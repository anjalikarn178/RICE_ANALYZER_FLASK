import { readFile, stat } from "fs/promises";
import path from "path";

const previewPath = path.resolve(process.cwd(), "..", "test_preview.jpg");

export const runtime = "nodejs";

export async function GET() {
  try {
    const [file, meta] = await Promise.all([readFile(previewPath), stat(previewPath)]);

    return new Response(new Uint8Array(file), {
      status: 200,
      headers: {
        "Content-Type": "image/jpeg",
        "Cache-Control": "no-store, max-age=0",
        "Last-Modified": meta.mtime.toUTCString(),
      },
    });
  } catch {
    return new Response(null, { status: 404 });
  }
}
