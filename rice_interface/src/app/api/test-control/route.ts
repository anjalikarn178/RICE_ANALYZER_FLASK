import { readFile, writeFile } from "fs/promises";
import path from "path";

type TestControlBody = {
  run?: boolean;
  videoPath?: string;
  realtime?: boolean;
  runId?: string;
};

const controlPath = path.resolve(process.cwd(), "..", "test.json");

export const runtime = "nodejs";

const defaultControl = {
  RUN: false,
  VIDEO_PATH: "",
  REALTIME: false,
  RUN_ID: "",
};

async function readControl(): Promise<Record<string, unknown>> {
  try {
    const raw = await readFile(controlPath, "utf-8");
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return { ...defaultControl };
  }
}

function serialize(config: Record<string, unknown>) {
  return {
    run: Boolean(config.RUN),
    videoPath: String(config.VIDEO_PATH ?? ""),
    realtime: Boolean(config.REALTIME),
    runId: String(config.RUN_ID ?? ""),
  };
}

export async function GET() {
  try {
    return Response.json(serialize(await readControl()), { status: 200 });
  } catch {
    return Response.json({ error: "Failed to read test control state" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as TestControlBody;
    const config = await readControl();

    if (typeof body.videoPath === "string") {
      config.VIDEO_PATH = body.videoPath;
    }

    if (typeof body.realtime === "boolean") {
      config.REALTIME = body.realtime;
    }

    // RUN_ID identifies this specific Start press, so the page can ignore status
    // left over from an earlier run.
    if (typeof body.runId === "string") {
      config.RUN_ID = body.runId;
    }

    if (typeof body.run === "boolean") {
      config.RUN = body.run;
    }

    await writeFile(controlPath, `${JSON.stringify(config, null, 4)}\n`, "utf-8");

    return Response.json(serialize(config), { status: 200 });
  } catch {
    return Response.json({ error: "Failed to update test control state" }, { status: 500 });
  }
}
