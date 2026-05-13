"""
Async ResNet18 classifier.
Runs in a background thread; call enqueue(crop_bgr, area) from any thread.
"""

import os
import queue
import threading

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

import data_io
from constants import BROKEN_25_THRESHOLD, BROKEN_50_THRESHOLD, RESNET18_CKPT_PATH


def _make_val_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )

def _build_resnet18(num_classes: int) -> nn.Module:
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


class AIClassifier:
    """
    Background-thread classifier.
    Pulls (crop_bgr, area) tuples from an internal queue and writes
    results to data.json via data_io.
    """

    def __init__(self):
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model, self._class_names, self._val_transform = self._load_model()
        self._softmax = nn.Softmax(dim=1)
        self._queue  = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[AI] Classifier ready on {self._device} (resnet18)")

    def _load_model(self) -> tuple[nn.Module, list[str], transforms.Compose]:
        if not os.path.exists(RESNET18_CKPT_PATH):
            raise FileNotFoundError(
                f"ResNet checkpoint not found at {RESNET18_CKPT_PATH}. "
                "Copy rice_resnet18_new_vids_best.pth into the app root."
            )

        payload = torch.load(str(RESNET18_CKPT_PATH), map_location=self._device)
        state_dict = payload.get("state_dict")
        class_names = payload.get("class_names")
        num_classes = payload.get("num_classes")

        if state_dict is None or class_names is None or num_classes is None:
            raise ValueError(
                f"Invalid checkpoint format in {RESNET18_CKPT_PATH}. "
                "Expected keys: state_dict, class_names, num_classes."
            )

        class_names = list(class_names)
        num_classes = int(num_classes)

        model = _build_resnet18(num_classes=num_classes).to(self._device)
        model.load_state_dict(state_dict)
        model.eval()
        print(f"[AI] Loaded ResNet18 checkpoint from {RESNET18_CKPT_PATH} (classes={class_names})")
        return model, class_names, _make_val_transform(img_size=128)

    def _classify(self, crop_bgr: np.ndarray, area: float) -> str:
        if 0 < area < BROKEN_25_THRESHOLD:
            return "broken_25"
        if BROKEN_25_THRESHOLD <= area < BROKEN_50_THRESHOLD:
            return "broken_50"
        try:
            rgb    = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            tensor = self._val_transform(Image.fromarray(rgb)).unsqueeze(0).to(self._device)
            with torch.no_grad():
                probs = self._softmax(self._model(tensor)).cpu().numpy()[0]
            idx = int(probs.argmax())
            if 0 <= idx < len(self._class_names):
                return self._class_names[idx]
            return "others"
        except Exception as e:
            print(f"[AI] Inference error: {e}")
            return "others"

    def _loop(self):
        while self._running:
            try:
                crop, area = self._queue.get(timeout=0.1)
                category = self._classify(crop, area)
                data_io.update_category(category)
                self._queue.task_done()
                data_io.update_queue_empty(self._queue.empty())
            except queue.Empty:
                pass
    def enqueue(self, crop_bgr: np.ndarray, area: float):
        self._queue.put((crop_bgr, area))
        data_io.update_queue_empty(False)


    def stop(self):
        self._running = False
