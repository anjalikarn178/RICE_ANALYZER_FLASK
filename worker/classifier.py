"""
Async EfficientNet-B0 classifier.
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
from torchvision.models import EfficientNet_B0_Weights

from constants import MODEL_PATH, CLASSES, BROKEN_AREA_THRESHOLD
import data_io


val_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def build_model(num_classes: int) -> nn.Module:
    model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    for p in model.parameters():
        p.requires_grad = False
    in_f = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3), nn.Linear(in_f, 512),    nn.BatchNorm1d(512),
        nn.Dropout(0.3), nn.Linear(512, 256),      nn.BatchNorm1d(256),
        nn.Dropout(0.3), nn.Linear(256, num_classes),
    )
    return model


class AIClassifier:
    """
    Background-thread classifier.
    Pulls (crop_bgr, area) tuples from an internal queue and writes
    results to data.json via data_io.
    """

    def __init__(self):
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model  = self._load_model()
        self._softmax = nn.Softmax(dim=1)
        self._queue  = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[AI] Classifier ready on {self._device}")

    def _load_model(self) -> nn.Module:
        model = build_model(len(CLASSES)).to(self._device)
        if os.path.exists(MODEL_PATH):
            model.load_state_dict(
                torch.load(MODEL_PATH, map_location=self._device, weights_only=True)
            )
            print(f"[AI] Loaded weights from {MODEL_PATH}")
        else:
            print(f"[AI] WARNING: {MODEL_PATH} not found — using random weights")
        model.eval()
        return model

    def _classify(self, crop_bgr: np.ndarray, area: float) -> str:
        if 0 < area < BROKEN_AREA_THRESHOLD:
            return "broken"
        try:
            rgb    = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            tensor = val_transform(Image.fromarray(rgb)).unsqueeze(0).to(self._device)
            with torch.no_grad():
                probs = self._softmax(self._model(tensor)).cpu().numpy()[0]
            return CLASSES[int(probs.argmax())]
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
