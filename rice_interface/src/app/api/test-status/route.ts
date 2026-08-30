import { readFile } from "fs/promises";
import path from "path";

const statusPath = path.resolve(process.cwd(), "..", "test_status.json");

// The worker refreshes updated_at about twice a second. Anything older than this
// means the status file was left behind by a worker that is no longer running.
const heartbeatTimeoutMs = 5000;

export const runtime = "nodejs";

export async function GET() {
  try {
    const raw = await readFile(statusPath, "utf-8");
    const status = JSON.parse(raw) as Record<string, unknown>;
    const updatedAt = Number(status.updated_at) || 0;
    const ageMs = Date.now() - updatedAt * 1000;

    return Response.json(
      {
        state: String(status.state ?? "idle"),
        video: String(status.video ?? ""),
        frame: Number(status.frame) || 0,
        totalFrames: Number(status.total_frames) || 0,
        message: String(status.message ?? ""),
        runId: String(status.run_id ?? ""),
        updatedAt,
        workerOnline: updatedAt > 0 && ageMs < heartbeatTimeoutMs,
      },
      { status: 200 }
    );
  } catch {
    // No status file yet — the video worker has never run.
    return Response.json(
      {
        state: "idle",
        video: "",
        frame: 0,
        totalFrames: 0,
        message: "",
        runId: "",
        updatedAt: 0,
        workerOnline: false,
      },
      { status: 200 }
    );
  }
}
