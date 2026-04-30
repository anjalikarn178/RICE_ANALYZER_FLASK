import os

PI_IP = "192.168.50.1"
PORT = 8000
EXPECTED_FPS = 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

CONFIG_FILE = os.path.join(PARENT_DIR, "cam.json")
DATA_FILE = os.path.join(PARENT_DIR, "data.json")

CHECK_INTERVAL = 0.5

URL = f"tcp://{PI_IP}:{PORT}"

CATEGORIES = ["white", "chalky", "broken", "brown", "yellow", "others"]

# Model
MODEL_PATH = os.path.join(PARENT_DIR, "rice_model.pth")
CLASSES = ["brown", "chalky", "white", "yellow"]   # must match training order
BROKEN_AREA_THRESHOLD = 300                         # px² — grains below this are broken