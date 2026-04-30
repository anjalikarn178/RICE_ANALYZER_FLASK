import { mkdir, readFile, writeFile } from "fs/promises";
import path from "path";

const dataPath = path.resolve(process.cwd(), "..", "data.json");
const logsDirPath = path.resolve(process.cwd(), "..", "logs");

type DataActionBody = {
  action?: "reset" | "save";
};

type CounterData = {
  count: number;
  white: number;
  chalky: number;
  broken: number;
  brown: number;
  yellow: number;
  others: number;
};

const emptyCounterData: CounterData = {
  count: 0,
  white: 0,
  chalky: 0,
  broken: 0,
  brown: 0,
  yellow: 0,
  others: 0,
};

function getLogFileName() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  const year = now.getFullYear();
  const month = pad(now.getMonth() + 1);
  const day = pad(now.getDate());
  const hours = pad(now.getHours());
  const minutes = pad(now.getMinutes());
  const seconds = pad(now.getSeconds());

  return `log(${year}-${month}-${day}_${hours}-${minutes}-${seconds}).json`;
}

async function readCounterData() {
  const raw = await readFile(dataPath, "utf-8");
  return JSON.parse(raw) as Record<string, unknown>;
}

export const runtime = "nodejs";

export async function GET() {
  try {
    const data = await readCounterData();

    return Response.json(data, { status: 200 });
  } catch {
    return Response.json({ error: "Failed to read data" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as DataActionBody;

    if (body.action === "reset") {
      await writeFile(dataPath, `${JSON.stringify(emptyCounterData, null, 4)}\n`, "utf-8");
      return Response.json(emptyCounterData, { status: 200 });
    }

    if (body.action === "save") {
      const data = await readCounterData();
      const fileName = getLogFileName();
      const filePath = path.resolve(logsDirPath, fileName);

      await mkdir(logsDirPath, { recursive: true });

      await writeFile(filePath, `${JSON.stringify(data, null, 4)}\n`, "utf-8");

      return Response.json({ ok: true, fileName: `logs/${fileName}` }, { status: 200 });
    }

    return Response.json({ error: "Invalid action" }, { status: 400 });
  } catch {
    return Response.json({ error: "Failed to process data action" }, { status: 500 });
  }
}