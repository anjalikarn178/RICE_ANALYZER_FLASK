import { createWriteStream } from "fs";
import { mkdir, readdir, stat, unlink } from "fs/promises";
import path from "path";
import { Readable } from "stream";
import { pipeline } from "stream/promises";
import type { ReadableStream as NodeWebReadableStream } from "stream/web";

const videoDirPath = path.resolve(process.cwd(), "..", "test_videos");

const allowedExtensions = new Set([".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm"]);

export const runtime = "nodejs";
export const maxDuration = 600;

function sanitizeName(rawName: string) {
  const base = path.basename(rawName).replace(/[^a-zA-Z0-9._-]/g, "_");
  return base.replace(/^\.+/, "") || "upload.mp4";
}

async function uniquePath(fileName: string) {
  const ext = path.extname(fileName);
  const stem = path.basename(fileName, ext);

  for (let i = 0; i < 1000; i += 1) {
    const candidate = i === 0 ? fileName : `${stem}-${i}${ext}`;
    const fullPath = path.join(videoDirPath, candidate);
    try {
      await stat(fullPath);
    } catch {
      return { fileName: candidate, fullPath };
    }
  }

  const fallback = `${stem}-${Date.now()}${ext}`;
  return { fileName: fallback, fullPath: path.join(videoDirPath, fallback) };
}

export async function GET() {
  try {
    await mkdir(videoDirPath, { recursive: true });
    const entries = await readdir(videoDirPath);

    const videos = (
      await Promise.all(
        entries
          .filter((entry) => allowedExtensions.has(path.extname(entry).toLowerCase()))
          .map(async (entry) => {
            const meta = await stat(path.join(videoDirPath, entry));
            return {
              fileName: entry,
              videoPath: `test_videos/${entry}`,
              sizeBytes: meta.size,
              modifiedAt: meta.mtimeMs,
            };
          })
      )
    ).sort((a, b) => b.modifiedAt - a.modifiedAt);

    return Response.json({ videos }, { status: 200 });
  } catch {
    return Response.json({ error: "Failed to list test videos" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    if (!request.body) {
      return Response.json({ error: "Missing file body" }, { status: 400 });
    }

    const requestedName = sanitizeName(request.headers.get("x-file-name") ?? "upload.mp4");

    if (!allowedExtensions.has(path.extname(requestedName).toLowerCase())) {
      return Response.json(
        { error: `Unsupported file type. Allowed: ${[...allowedExtensions].join(", ")}` },
        { status: 400 }
      );
    }

    await mkdir(videoDirPath, { recursive: true });
    const { fileName, fullPath } = await uniquePath(requestedName);

    // Stream straight to disk so large videos never sit in memory.
    await pipeline(
      Readable.fromWeb(request.body as unknown as NodeWebReadableStream),
      createWriteStream(fullPath)
    );

    const meta = await stat(fullPath);

    return Response.json(
      {
        ok: true,
        fileName,
        videoPath: `test_videos/${fileName}`,
        sizeBytes: meta.size,
      },
      { status: 200 }
    );
  } catch {
    return Response.json({ error: "Failed to upload video" }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const requested = new URL(request.url).searchParams.get("fileName") ?? "";
    const fileName = path.basename(requested);
    const fullPath = path.join(videoDirPath, fileName);

    if (!fileName || path.dirname(fullPath) !== videoDirPath) {
      return Response.json({ error: "Invalid file name" }, { status: 400 });
    }

    await unlink(fullPath);

    return Response.json({ ok: true, fileName }, { status: 200 });
  } catch {
    return Response.json({ error: "Failed to delete video" }, { status: 500 });
  }
}
