"use client";

/**
 * Temporary testing space: run a pre-recorded video through the same
 * detection + classification pipeline used for the live Pi feed.
 *
 * Requires the video worker to be running:  python worker/test_main.py
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import pageStyles from "../page.module.css";
import styles from "./test.module.css";

type CounterKey =
  | "count"
  | "chalky"
  | "yellow"
  | "white"
  | "brown"
  | "broken"
  | "others";

type CounterData = Record<CounterKey, number>;

type TestVideo = {
  fileName: string;
  videoPath: string;
  sizeBytes: number;
  modifiedAt: number;
};

type TestStatus = {
  state: string;
  video: string;
  frame: number;
  totalFrames: number;
  message: string;
  runId: string;
  updatedAt: number;
  workerOnline: boolean;
};

const counterCards: Array<{ label: string; key: CounterKey }> = [
  { label: "Count", key: "count" },
  { label: "Chalky Rice", key: "chalky" },
  { label: "Yellow Rice", key: "yellow" },
  { label: "White Rice", key: "white" },
  { label: "Brown Rice", key: "brown" },
  { label: "Broken Rice", key: "broken" },
  { label: "Other", key: "others" },
];

const emptyCounterData: CounterData = {
  count: 0,
  chalky: 0,
  yellow: 0,
  white: 0,
  brown: 0,
  broken: 0,
  others: 0,
};

const emptyStatus: TestStatus = {
  state: "idle",
  video: "",
  frame: 0,
  totalFrames: 0,
  message: "",
  runId: "",
  updatedAt: 0,
  workerOnline: false,
};

function toCounterData(raw: Partial<Record<CounterKey, unknown>>): CounterData {
  return {
    count: Number(raw.count) || 0,
    chalky: Number(raw.chalky) || 0,
    yellow: Number(raw.yellow) || 0,
    white: Number(raw.white) || 0,
    brown: Number(raw.brown) || 0,
    broken: Number(raw.broken) || 0,
    others: Number(raw.others) || 0,
  };
}

function formatSize(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function VideoTestPage() {
  const [videos, setVideos] = useState<TestVideo[]>([]);
  const [selectedPath, setSelectedPath] = useState("");
  const [realtime, setRealtime] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState<TestStatus>(emptyStatus);
  const [counterData, setCounterData] = useState<CounterData>(emptyCounterData);
  const [queueEmpty, setQueueEmpty] = useState(true);
  const [uploadPercent, setUploadPercent] = useState(-1);
  const [isBusy, setIsBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const [previewStamp, setPreviewStamp] = useState(0);
  const [hasPreview, setHasPreview] = useState(false);

  const [runId, setRunId] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchVideos = useCallback(async () => {
    try {
      const res = await fetch("/api/test-video", { cache: "no-store" });
      if (!res.ok) throw new Error("list failed");
      const data = (await res.json()) as { videos?: TestVideo[] };
      setVideos(data.videos ?? []);
    } catch {
      setErrorMessage("Unable to list uploaded videos.");
    }
  }, []);

  const fetchControl = useCallback(async () => {
    try {
      const res = await fetch("/api/test-control", { cache: "no-store" });
      if (!res.ok) throw new Error("control failed");
      const data = (await res.json()) as {
        run?: boolean;
        videoPath?: string;
        realtime?: boolean;
        runId?: string;
      };
      setIsRunning(Boolean(data.run));
      setRealtime(Boolean(data.realtime));
      setRunId((prev) => prev || String(data.runId ?? ""));
      setSelectedPath((prev) => prev || String(data.videoPath ?? ""));
    } catch {
      setErrorMessage("Unable to read test control state.");
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/test-status", { cache: "no-store" });
      if (!res.ok) throw new Error("status failed");
      setStatus((await res.json()) as TestStatus);
    } catch {
      setStatus(emptyStatus);
    }
  }, []);

  const fetchQueueState = useCallback(async () => {
    try {
      const res = await fetch("/api/count-completed", { cache: "no-store" });
      if (!res.ok) throw new Error("queue failed");
      const data = (await res.json()) as { queueEmpty?: boolean };
      setQueueEmpty(Boolean(data.queueEmpty));
    } catch {
      setQueueEmpty(true);
    }
  }, []);

  const fetchCounterData = useCallback(async () => {
    try {
      const res = await fetch("/api/data", { cache: "no-store" });
      if (!res.ok) throw new Error("data failed");
      const data = (await res.json()) as Partial<Record<CounterKey, unknown>>;
      setCounterData(toCounterData(data));
    } catch {
      setErrorMessage("Unable to read data values.");
    }
  }, []);

  const postControl = useCallback(
    async (body: {
      run?: boolean;
      videoPath?: string;
      realtime?: boolean;
      runId?: string;
    }) => {
      const res = await fetch("/api/test-control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to update test control state");
      const data = (await res.json()) as { run?: boolean; realtime?: boolean };
      setIsRunning(Boolean(data.run));
      setRealtime(Boolean(data.realtime));
    },
    []
  );

  useEffect(() => {
    fetchVideos();
    fetchControl();
    fetchStatus();
    fetchQueueState();
    fetchCounterData();
  }, [fetchVideos, fetchControl, fetchStatus, fetchQueueState, fetchCounterData]);

  // Poll status, counters and queue while the worker has anything in flight.
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStatus();
      fetchQueueState();
      fetchCounterData();
    }, 1000);

    return () => clearInterval(interval);
  }, [fetchStatus, fetchQueueState, fetchCounterData]);

  // Refresh the annotated preview frame while a video is being processed.
  useEffect(() => {
    if (status.state !== "running") return;

    const interval = setInterval(() => setPreviewStamp(Date.now()), 500);
    return () => clearInterval(interval);
  }, [status.state]);

  // Status only describes the current run when its run id matches the one we wrote
  // on Start. Anything else is left over from an earlier run (or another tab).
  const statusIsForThisRun = Boolean(runId) && status.runId === runId;

  // The worker leaves RUN=true when it reaches the end of a video; flip it back so
  // the run is finished and a new one can start. Gated on the run id — otherwise a
  // stale "done" in the status file cancels the run the user just started.
  useEffect(() => {
    if (!isRunning || !statusIsForThisRun) return;

    if (status.state === "done" || status.state === "error") {
      postControl({ run: false }).catch(() => undefined);
    }
  }, [isRunning, statusIsForThisRun, status.state, postControl]);

  const uploadVideo = (file: File) => {
    setErrorMessage("");
    setInfoMessage("");
    setUploadPercent(0);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/test-video");
    xhr.setRequestHeader("x-file-name", file.name);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setUploadPercent(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = async () => {
      setUploadPercent(-1);
      if (fileInputRef.current) fileInputRef.current.value = "";

      if (xhr.status < 200 || xhr.status >= 300) {
        let message = "Upload failed.";
        try {
          message = (JSON.parse(xhr.responseText) as { error?: string }).error ?? message;
        } catch {
          /* keep default message */
        }
        setErrorMessage(message);
        return;
      }

      const data = JSON.parse(xhr.responseText) as { videoPath?: string; fileName?: string };
      setInfoMessage(`Uploaded ${data.fileName ?? "video"}.`);
      await fetchVideos();

      if (data.videoPath) {
        setSelectedPath(data.videoPath);
        await postControl({ videoPath: data.videoPath }).catch(() => undefined);
      }
    };

    xhr.onerror = () => {
      setUploadPercent(-1);
      setErrorMessage("Upload failed.");
    };

    xhr.send(file);
  };

  const selectVideo = async (videoPath: string) => {
    if (isRunning) return;
    setSelectedPath(videoPath);
    setErrorMessage("");
    setInfoMessage("");
    try {
      await postControl({ videoPath });
    } catch {
      setErrorMessage("Unable to select that video.");
    }
  };

  const deleteVideo = async (fileName: string) => {
    setIsBusy(true);
    setErrorMessage("");
    setInfoMessage("");

    try {
      const res = await fetch(`/api/test-video?fileName=${encodeURIComponent(fileName)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("delete failed");

      if (selectedPath === `test_videos/${fileName}`) {
        setSelectedPath("");
        await postControl({ videoPath: "" });
      }
      await fetchVideos();
    } catch {
      setErrorMessage("Unable to delete that video.");
    } finally {
      setIsBusy(false);
    }
  };

  const startRun = async () => {
    if (!selectedPath) {
      setErrorMessage("Select or upload a video first.");
      return;
    }

    if (!status.workerOnline) {
      setErrorMessage(
        "The video worker is not running — start it with: python worker/test_main.py"
      );
      return;
    }

    setIsBusy(true);
    setErrorMessage("");
    setInfoMessage("");

    const nextRunId = `${Date.now()}`;

    try {
      await postControl({
        run: true,
        videoPath: selectedPath,
        realtime,
        runId: nextRunId,
      });
      setRunId(nextRunId);
      setHasPreview(false);
      await fetchCounterData();
    } catch {
      setErrorMessage("Unable to start the video run.");
    } finally {
      setIsBusy(false);
    }
  };

  const stopRun = async () => {
    setIsBusy(true);
    setErrorMessage("");

    try {
      await postControl({ run: false });
    } catch {
      setErrorMessage("Unable to stop the video run.");
    } finally {
      setIsBusy(false);
    }
  };

  const resetCounters = async () => {
    setIsBusy(true);
    setErrorMessage("");
    setInfoMessage("");

    try {
      const res = await fetch("/api/data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset" }),
      });
      if (!res.ok) throw new Error("reset failed");
      setCounterData(toCounterData(await res.json()));
    } catch {
      setErrorMessage("Unable to reset data values.");
    } finally {
      setIsBusy(false);
    }
  };

  const saveOutput = async () => {
    setIsBusy(true);
    setErrorMessage("");
    setInfoMessage("");

    try {
      const res = await fetch("/api/data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save" }),
      });
      if (!res.ok) throw new Error("save failed");
      const data = (await res.json()) as { fileName?: string };
      setInfoMessage(data.fileName ? `Saved to ${data.fileName}` : "Saved output file.");
    } catch {
      setErrorMessage("Unable to save output file.");
    } finally {
      setIsBusy(false);
    }
  };

  // Frame/progress numbers belong to the current run only.
  const shownFrame = statusIsForThisRun ? status.frame : 0;
  const shownTotalFrames = statusIsForThisRun ? status.totalFrames : 0;

  const isProcessing = statusIsForThisRun && status.state === "running";
  const isClassifying = !queueEmpty;
  const progressPercent =
    shownTotalFrames > 0
      ? Math.min(100, Math.round((shownFrame / shownTotalFrames) * 100))
      : 0;

  const statusLabel = (() => {
    if (!status.workerOnline) return "Video worker offline";
    if (isProcessing) return `Processing ${status.video}`;
    if (isRunning && !statusIsForThisRun) return "Waiting for the worker to pick up the run...";
    if (isClassifying) return "Classifying queued grains...";

    if (statusIsForThisRun) {
      if (status.state === "error") return `Error: ${status.message}`;
      if (status.state === "done") return `Finished ${status.video}`;
      if (status.state === "stopped") return `Stopped ${status.video}`;
    }

    return "Idle";
  })();

  return (
    <div className={pageStyles.page}>
      <main className={pageStyles.main}>
        <header className={pageStyles.header}>
          <p className={styles.testBadge}>Temporary test space</p>
          <h1 className={pageStyles.title}>Video File Analyzer</h1>
          <p className={pageStyles.subtitle}>
            Upload a recorded clip and push it through the same detection, tracking and
            classification pipeline used for the live Raspberry Pi feed. Requires the video
            worker: <code>python worker/test_main.py</code>
          </p>
          <Link className={styles.backLink} href="/">
            ← Back to live dashboard
          </Link>
        </header>

        <section className={pageStyles.controlPanel}>
          <h2 className={styles.panelTitle}>1. Pick a video</h2>
          <p className={styles.panelHint}>
            Uploads are stored in <code>test_videos/</code> at the project root.
          </p>

          <div className={styles.uploadRow}>
            <input
              ref={fileInputRef}
              className={styles.fileInput}
              type="file"
              accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,video/webm,.mp4,.avi,.mov,.mkv,.m4v,.webm"
              disabled={isRunning || uploadPercent >= 0}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) uploadVideo(file);
              }}
            />
          </div>

          {uploadPercent >= 0 && (
            <div className={styles.progressTrack}>
              <div className={styles.progressBar} style={{ width: `${uploadPercent}%` }} />
            </div>
          )}

          {videos.length === 0 ? (
            <p className={styles.emptyList}>No videos uploaded yet.</p>
          ) : (
            <div className={styles.videoList}>
              {videos.map((video) => (
                <div
                  key={video.fileName}
                  className={`${styles.videoRow} ${
                    selectedPath === video.videoPath ? styles.videoRowSelected : ""
                  }`}
                  role="button"
                  tabIndex={0}
                  onClick={() => selectVideo(video.videoPath)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      selectVideo(video.videoPath);
                    }
                  }}
                >
                  <span className={styles.videoName}>{video.fileName}</span>
                  <span className={styles.videoMeta}>{formatSize(video.sizeBytes)}</span>
                  <button
                    type="button"
                    className={styles.deleteButton}
                    disabled={isRunning || isBusy}
                    onClick={(event) => {
                      event.stopPropagation();
                      deleteVideo(video.fileName);
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}

          <label className={styles.optionRow}>
            <input
              type="checkbox"
              checked={realtime}
              disabled={isRunning}
              onChange={(event) => {
                setRealtime(event.target.checked);
                postControl({ realtime: event.target.checked }).catch(() => undefined);
              }}
            />
            Play at the video&apos;s own frame rate (slower, closer to the live feed)
          </label>
        </section>

        <section className={pageStyles.controlPanel}>
          <h2 className={styles.panelTitle}>2. Run the pipeline</h2>

          <div className={pageStyles.statusRow}>
            <span
              className={`${pageStyles.statusDot} ${
                status.workerOnline && (isProcessing || isClassifying)
                  ? pageStyles.running
                  : pageStyles.stopped
              }`}
            />
            <p className={pageStyles.statusText}>{statusLabel}</p>
          </div>

          <p className={styles.runInfo}>
            <span>
              Frame {shownFrame}
              {shownTotalFrames > 0 ? ` / ${shownTotalFrames}` : ""}
            </span>
            <span>Selected: {selectedPath || "none"}</span>
          </p>

          {shownTotalFrames > 0 && (
            <div className={styles.progressTrack}>
              <div className={styles.progressBar} style={{ width: `${progressPercent}%` }} />
            </div>
          )}

          <div className={pageStyles.actionRow}>
            <button
              className={`${pageStyles.button} ${pageStyles.startButton}`}
              onClick={startRun}
              disabled={isBusy || isRunning || !selectedPath || !status.workerOnline}
            >
              Start
            </button>
            <button
              className={`${pageStyles.button} ${pageStyles.stopButton}`}
              onClick={stopRun}
              disabled={isBusy || !isRunning}
            >
              Stop
            </button>
            <button
              className={`${pageStyles.button} ${pageStyles.resetButton}`}
              onClick={resetCounters}
              disabled={isBusy || isRunning}
            >
              Reset
            </button>
            <button
              className={`${pageStyles.button} ${pageStyles.saveButton}`}
              onClick={saveOutput}
              disabled={isBusy}
            >
              Save
            </button>
          </div>

          {!status.workerOnline && (
            <p className={pageStyles.warning}>
              Video worker offline — nothing will process. Start it with{" "}
              <code>python worker/test_main.py</code> (run it instead of{" "}
              <code>worker/main.py</code>, not alongside it).
            </p>
          )}

          {statusIsForThisRun && status.message && status.state !== "running" && (
            <p className={styles.panelHint}>{status.message}</p>
          )}

          {errorMessage && <p className={pageStyles.error}>{errorMessage}</p>}
          {infoMessage && <p className={styles.panelHint}>{infoMessage}</p>}
        </section>

        <section className={pageStyles.controlPanel}>
          <h2 className={styles.panelTitle}>Detection preview</h2>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            className={styles.previewFrame}
            src={`/api/test-preview?t=${previewStamp}`}
            alt="Annotated frame from the video worker"
            style={hasPreview ? undefined : { display: "none" }}
            onLoad={() => setHasPreview(true)}
            onError={() => setHasPreview(false)}
          />
          {!hasPreview && (
            <div className={styles.previewPlaceholder}>
              The annotated frame appears here once the worker starts processing.
            </div>
          )}
        </section>

        <section className={pageStyles.counterGrid}>
          {counterCards.map((counterCard) => (
            <article key={counterCard.label} className={pageStyles.counterCard}>
              <p className={pageStyles.counterLabel}>{counterCard.label}</p>
              <p className={pageStyles.counterValue}>{counterData[counterCard.key]}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
