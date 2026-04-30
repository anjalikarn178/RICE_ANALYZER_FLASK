"""
Thread-safe read/write for data.json.
Both processor.py (main thread) and classifier.py (background thread) write here,
so all access goes through a single lock.
"""

import json
import threading
from constants import DATA_FILE, CATEGORIES

_lock = threading.Lock()


def update_total(n: int):
    """Add n to the total grain count."""
    with _lock:
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            data["count"] += n
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Total update failed: {e}")


def update_category(category: str):
    """Increment a specific rice category count."""
    with _lock:
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            if category in data:
                data[category] += 1
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Category update failed: {e}")


def reset():
    """Reset all counts to zero."""
    with _lock:
        data = {"count": 0}
        for c in CATEGORIES:
            data[c] = 0
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Reset failed: {e}")
