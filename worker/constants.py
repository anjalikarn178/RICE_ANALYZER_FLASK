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

CATEGORIES = ["white", "chalky", "broken_25", "broken_50", "brown", "yellow", "black", "others"]

# Model
RESNET18_CKPT_PATH = os.path.join(PARENT_DIR, "rice_resnet18_new_vids_best.pth")
BROKEN_25_THRESHOLD = 150                           # px² — grains below this are 25% broken
BROKEN_50_THRESHOLD = 300                           # px² — grains below this are 50% broken