"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./page.module.css";

type CounterKey = "count" | "chalky" | "yellow" | "white" | "brown" | "broken" | "others";

type CounterData = Record<CounterKey, number>;

const counterCards: Array<{ label: string; key: CounterKey }> = [
  { label: "Count", key: "count" }, // Total will be calculated as the sum of all types
  { label: "Chalky Rice", key: "chalky" },
  { label: "Yellow Rice", key: "yellow" },
  { label: "White Rice", key: "white" },
  { label: "Brown Rice", key: "brown" },
  { label: "Broken Rice", key: "broken" },
  { label: "Other", key: "others" },
];

export default function Home() {
  const [isPiConnected, setIsPiConnected] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [isCameraRunning, setIsCameraRunning] = useState(false);
  const [isUpdatingCamera, setIsUpdatingCamera] = useState(false);
  const [isSavingOutput, setIsSavingOutput] = useState(false);
  const [isCompletionPopupVisible, setIsCompletionPopupVisible] = useState(false);
  const [hasDismissedCompletionPopup, setHasDismissedCompletionPopup] = useState(false);
  const [cameraControlError, setCameraControlError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [counterData, setCounterData] = useState<CounterData>({
    count: 0,
    chalky: 0,
    yellow: 0,
    white: 0,
    brown: 0,
    broken: 0,
    others: 0,
  });

  const classifiedRiceCount =
    counterData.chalky +
    counterData.yellow +
    counterData.white +
    counterData.brown +
    counterData.broken +
    counterData.others;
  const isClassificationDone =
    counterData.count > 0 && classifiedRiceCount === counterData.count;

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
        broken: Number(data.broken) || 0,
        others: Number(data.others) || 0,
      });
    } catch {
      setCameraControlError("Unable to read data values.");
    }
  }, []);

  useEffect(() => {
    checkPiConnection();
    fetchCameraState();

    const interval = setInterval(() => {
      checkPiConnection();
    }, 1000);

    return () => clearInterval(interval);
  }, [checkPiConnection, fetchCameraState]);

  useEffect(() => {
    if (!isCameraRunning) return;

    fetchCounterData();

    const interval = setInterval(() => {
      fetchCounterData();
    }, 1000);

    return () => clearInterval(interval);
  }, [isCameraRunning, fetchCounterData]);

  useEffect(() => {
    if (isClassificationDone) {
      if (!hasDismissedCompletionPopup) {
        setIsCompletionPopupVisible(true);
      }
      return;
    }

    setIsCompletionPopupVisible(false);
    setHasDismissedCompletionPopup(false);
  }, [isClassificationDone, hasDismissedCompletionPopup]);

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
        broken: Number(data.broken) || 0,
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
      {isCompletionPopupVisible && (
        <aside className={styles.completionPopup} role="status" aria-live="polite">
          <p className={styles.completionPopupTitle}>Classification Done</p>
          <p className={styles.completionPopupText}>
            The count of all rice types now matches the total rice count.
          </p>
          <button
            className={styles.completionCloseButton}
            onClick={() => {
              setIsCompletionPopupVisible(false);
              setHasDismissedCompletionPopup(true);
            }}
          >
            Close
          </button>
        </aside>
      )}

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

          <p className={styles.classificationProgress}>
            Classified: {classifiedRiceCount} / {counterData.count}
          </p>

          {isClassificationDone && (
            <p className={styles.classificationDone}>Classification is done.</p>
          )}

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

          {saveMessage && <p className={styles.connectionWarning}>{saveMessage}</p>}

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
    </div>
  );
}