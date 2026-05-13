"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./page.module.css";

type CounterKey =
  | "count"
  | "chalky"
  | "yellow"
  | "white"
  | "brown"
  | "broken_25"
  | "broken_50"
  | "black"
  | "others";

type CounterData = Record<CounterKey, number>;

const counterCards: Array<{ label: string; key: CounterKey }> = [
  { label: "Count", key: "count" },
  { label: "Chalky Rice", key: "chalky" },
  { label: "Yellow Rice", key: "yellow" },
  { label: "White Rice", key: "white" },
  { label: "Brown Rice", key: "brown" },
  { label: "25% Broken", key: "broken_25" },
  { label: "50% Broken", key: "broken_50" },
  { label: "Black Rice", key: "black" },
  { label: "Other", key: "others" },
];

export default function Home() {
  const [isPiConnected, setIsPiConnected] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [isCameraRunning, setIsCameraRunning] = useState(false);
  const [isUpdatingCamera, setIsUpdatingCamera] = useState(false);
  const [isSavingOutput, setIsSavingOutput] = useState(false);
  const [cameraControlError, setCameraControlError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [showFinished, setShowFinished] = useState(false);
  const [queueTrueStreak, setQueueTrueStreak] = useState(0);

  const [finishedToastVisible, setFinishedToastVisible] = useState(false);

  const [counterData, setCounterData] = useState<CounterData>({
    count: 0,
    chalky: 0,
    yellow: 0,
    white: 0,
    brown: 0,
    broken_25: 0,
    broken_50: 0,
    black: 0,
    others: 0,
  });

  const checkPiConnection = useCallback(async () => {
    try {
      const res = await fetch("/api/ping", { cache: "no-store" });

      if (!res.ok) {
        throw new Error("Ping failed");
      }

      const data = await res.json();
      setIsPiConnected(Boolean(data.connected));
    } catch {
      setIsPiConnected(false);
    } finally {
      setIsChecking(false);
    }
  }, []);

  const fetchQueueState = useCallback(async () => {
    try {
      const res = await fetch("/api/count-completed", { cache: "no-store" });

      if (!res.ok) {
        throw new Error("Failed to fetch queue state");
      }

      const data = await res.json();
      const isQueueEmpty = Boolean(data.queueEmpty);

      setQueueTrueStreak((prev) => {
        const nextStreak = isQueueEmpty ? prev + 1 : 0;
        const nextShowFinished = nextStreak >= 3;

        setShowFinished((prevShowFinished) => {
          if (!prevShowFinished && nextShowFinished) {
            setFinishedToastVisible(true);
          }
          return nextShowFinished;
        });

        return nextShowFinished ? 3 : nextStreak;
      });
    } catch {
      setQueueTrueStreak(0);
      setShowFinished(false);
    }
  }, []);

  const fetchCameraState = useCallback(async () => {
    try {
      const res = await fetch("/api/camera", { cache: "no-store" });

      if (!res.ok) {
        throw new Error("Failed to fetch camera state");
      }

      const data = await res.json();
      setIsCameraRunning(Boolean(data.cameraRun));
    } catch {
      setCameraControlError("Unable to read camera state.");
    }
  }, []);

  const fetchCounterData = useCallback(async () => {
    try {
      const res = await fetch("/api/data", { cache: "no-store" });

      if (!res.ok) {
        throw new Error("Failed to fetch counter data");
      }

      const data = (await res.json()) as Partial<Record<CounterKey, unknown>>;

      setCounterData({
        count: Number(data.count) || 0,
        chalky: Number(data.chalky) || 0,
        yellow: Number(data.yellow) || 0,
        white: Number(data.white) || 0,
        brown: Number(data.brown) || 0,
        broken_25: Number(data.broken_25) || 0,
        broken_50: Number(data.broken_50) || 0,
        black: Number(data.black) || 0,
        others: Number(data.others) || 0,
      });
    } catch {
      setCameraControlError("Unable to read data values.");
    }
  }, []);

  useEffect(() => {
    checkPiConnection();
    fetchCameraState();
    fetchQueueState();

    const interval = setInterval(() => {
      checkPiConnection();
      fetchQueueState();
    }, 1000);

    return () => clearInterval(interval);
  }, [checkPiConnection, fetchCameraState, fetchQueueState]);

  useEffect(() => {
    if (!isCameraRunning) return;

    fetchCounterData();

    const interval = setInterval(() => {
      fetchCounterData();
    }, 1000);

    return () => clearInterval(interval);
  }, [isCameraRunning, fetchCounterData]);

  const setCameraRunState = async (cameraRun: boolean) => {
    setIsUpdatingCamera(true);
    setCameraControlError("");
    setSaveMessage("");

    try {
      const res = await fetch("/api/camera", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ cameraRun }),
      });

      if (!res.ok) {
        throw new Error("Failed to update camera state");
      }

      const data = await res.json();
      setIsCameraRunning(Boolean(data.cameraRun));
      return true;
    } catch {
      setCameraControlError("Unable to update camera state.");
      return false;
    } finally {
      setIsUpdatingCamera(false);
    }
  };

  const resetCounterData = async () => {
    setIsUpdatingCamera(true);
    setCameraControlError("");
    setSaveMessage("");

    try {
      const res = await fetch("/api/data", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "reset" }),
      });

      if (!res.ok) {
        throw new Error("Failed to reset data");
      }

      const data = (await res.json()) as Partial<Record<CounterKey, unknown>>;

      setCounterData({
        count: Number(data.count) || 0,
        chalky: Number(data.chalky) || 0,
        yellow: Number(data.yellow) || 0,
        white: Number(data.white) || 0,
        brown: Number(data.brown) || 0,
        broken_25: Number(data.broken_25) || 0,
        broken_50: Number(data.broken_50) || 0,
        black: Number(data.black) || 0,
        others: Number(data.others) || 0,
      });
    } catch {
      setCameraControlError("Unable to reset data values.");
    } finally {
      setIsUpdatingCamera(false);
    }
  };

  const saveCounterOutput = async () => {
    setIsSavingOutput(true);
    setCameraControlError("");
    setSaveMessage("");

    try {
      const res = await fetch("/api/data", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "save" }),
      });

      if (!res.ok) {
        throw new Error("Failed to save output");
      }

      const data = (await res.json()) as { fileName?: string };
      setSaveMessage(data.fileName ? `Saved to ${data.fileName}` : "Saved output file.");
    } catch {
      setCameraControlError("Unable to save output file.");
    } finally {
      setIsSavingOutput(false);
    }
  };

  const handleClick = async (action: string) => {
    if (isUpdatingCamera || isSavingOutput) return;

    const normalizedAction = action.toLowerCase();

    if (normalizedAction === "start") {
      if (!isPiConnected) return;
      const updated = await setCameraRunState(true);
      if (updated) {
        await fetchCounterData();
      }
    }

    if (normalizedAction === "stop") {
      if (!isPiConnected) return;
      await setCameraRunState(false);
    }

    if (normalizedAction === "reset") {
      await resetCounterData();
    }
  };

  const isStartDisabled =
    !isPiConnected || isUpdatingCamera || isSavingOutput || isCameraRunning;

  const isStopDisabled =
    !isPiConnected || isUpdatingCamera || isSavingOutput || !isCameraRunning;

  const isResetDisabled = isUpdatingCamera || isSavingOutput || isCameraRunning;
  const isSaveDisabled = isUpdatingCamera || isSavingOutput;

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <header className={styles.header}>
          <p className={styles.kicker}>Rice Interface</p>
          <h1 className={styles.title}>Flow Control Dashboard</h1>
          <p className={styles.subtitle}>Backend ping check every second.</p>
        </header>

        <section className={styles.controlPanel}>
          <div className={styles.statusRow}>
            <span
              className={`${styles.statusDot} ${
                isPiConnected ? styles.running : styles.stopped
              }`}
            />
            <p className={styles.statusText}>
              {isChecking
                ? "Checking connection..."
                : isPiConnected
                ? "Raspberry Pi is connected"
                : "Raspberry Pi is disconnected"}
            </p>
          </div>
          <div className={styles.statusRow}>
            <span
              className={`${styles.statusDot} ${
                showFinished ? styles.stopped : styles.running
              }`}
            />
            <p className={styles.statusText}>
              {showFinished ? "Not Processing" : "Processing"}
            </p>
          </div>

          <div className={styles.actionRow}>
            <button
              className={`${styles.button} ${styles.startButton}`}
              onClick={() => handleClick("Start")}
              disabled={isStartDisabled}
            >
              Start
            </button>

            <button
              className={`${styles.button} ${styles.stopButton}`}
              onClick={() => handleClick("Stop")}
              disabled={isStopDisabled}
            >
              Stop
            </button>

            <button
              className={`${styles.button} ${styles.resetButton}`}
              onClick={() => handleClick("Reset")}
              disabled={isResetDisabled}
            >
              Reset
            </button>

            <button
              className={`${styles.button} ${styles.saveButton}`}
              onClick={saveCounterOutput}
              disabled={isSaveDisabled}
            >
              Save
            </button>
          </div>

          {cameraControlError && (
            <p className={styles.connectionWarning}>{cameraControlError}</p>
          )}

          {saveMessage && (
            <p className={styles.connectionWarning}>{saveMessage}</p>
          )}

          {!isChecking && !isPiConnected && (
            <p className={styles.connectionWarning}>
              Connect to the Raspberry Pi to enable controls.
            </p>
          )}
        </section>

        <section className={styles.counterGrid}>
          {counterCards.map((counterCard) => (
            <article key={counterCard.label} className={styles.counterCard}>
              <p className={styles.counterLabel}>{counterCard.label}</p>
              <p className={styles.counterValue}>{counterData[counterCard.key]}</p>
            </article>
          ))}
        </section>
      </main>

      {finishedToastVisible && (
        <div className={styles.toastContainer}>
          <div className={styles.toastSuccess}>
            <span className={styles.toastMessage}>Processing done</span>
            <button
              type="button"
              className={styles.toastCloseButton}
              onClick={() => setFinishedToastVisible(false)}
              aria-label="Close notification"
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}