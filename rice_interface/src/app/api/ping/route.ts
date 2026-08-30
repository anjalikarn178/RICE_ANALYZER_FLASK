import { exec } from "child_process";

export async function GET(): Promise<Response> {
  return new Promise<Response>((resolve) => {
    // ping -n 1 -w 1000 192.168.50.1 for Windows
    exec("ping -c 1 -W 1 192.168.50.1", (error) => {
      if (error) {
        resolve(
          Response.json({ connected: false }, { status: 200 })
        );
      } else {
        resolve(
          Response.json({ connected: true }, { status: 200 })
        );
      }
    });
  });
}