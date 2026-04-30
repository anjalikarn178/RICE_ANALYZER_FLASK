import { readFile, writeFile } from "fs/promises";
import path from "path";

type QueueControlBody = {
  queueEmpty?: boolean;
};

const configPath = path.resolve(process.cwd(), "..", "queue.json");

export const runtime = "nodejs";

async function readQueueConfig() {
  const rawConfig = await readFile(configPath, "utf-8");
  return JSON.parse(rawConfig) as Record<string, unknown>;
}

export async function GET() {
  try {
    const config = await readQueueConfig();
    return Response.json(
      { queueEmpty: Boolean(config.QUEUE_EMPTY) },
      { status: 200 }
    );
  } catch {
    return Response.json(
      { error: "Failed to read queue state" },
      { status: 500 }
    );
  }
}
