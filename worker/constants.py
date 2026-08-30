import os

PI_IP = "192.168.50.1"
PORT = 8000
EXPECTED_FPS = 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

CONFIG_FILE = os.path.join(PARENT_DIR, "cam.json")
DATA_FILE = os.path.join(PARENT_DIR, "data.json")
QUEUE_FILE = os.path.join(PARENT_DIR, "queue.json")

CHECK_INTERVAL = 0.5

URL = f"tcp://{PI_IP}:{PORT}"

CATEGORIES = ["black", "white", "chalky", "broken", "brown", "yellow", "others"]

# Model
MODEL_PATH = os.path.join(PARENT_DIR, "rice_model.pth")
CLASSES = ["black", "brown", "chalky", "white", "yellow"]   # must match training order
BROKEN_AREA_THRESHOLD = 300                         # px² — grains below this are broken
# ── Video-file test harness (temporary; live pipeline is unaffected) ───────────
TEST_CONTROL_FILE = os.path.join(PARENT_DIR, "test.json")          # written by UI
TEST_STATUS_FILE  = os.path.join(PARENT_DIR, "test_status.json")   # written by worker
TEST_PREVIEW_FILE = os.path.join(PARENT_DIR, "test_preview.jpg")   # written by worker
TEST_VIDEO_DIR    = os.path.join(PARENT_DIR, "test_videos")        # uploaded videos
