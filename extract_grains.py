import os
import sys
import glob
import cv2
import numpy as np
import random
import uuid

# add worker to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "worker")))
from worker.grain_counter import detect_grains, GatedVelocityTracker, BackgroundCalibrator

# Output directories
OUT_DIR = "dataset_new"
TRAIN_DIR = os.path.join(OUT_DIR, "train")
VAL_DIR = os.path.join(OUT_DIR, "val")

# Make dirs for classes
CLASSES = ["black", "brown", "chalky", "white", "yellow"]
for split in [TRAIN_DIR, VAL_DIR]:
    for cls in CLASSES:
        os.makedirs(os.path.join(split, cls), exist_ok=True)

TOP_LINE_Y = 70
BOTTOM_LINE_Y = 650

def extract_video(video_path, cls_name):
    print(f"Extracting {video_path} for class {cls_name}...")
    cap = cv2.VideoCapture(video_path)
    
    bg_calibrator = BackgroundCalibrator(background_frames_needed=30, sample_every=5, threshold_margin=5)
    tracker = GatedVelocityTracker(max_missed=3, gate_radius=70.0, estimated_speed=145.0)

    extracted = []
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        if not bg_calibrator.is_calibrated:
            bg_calibrator.add_frame(frame)
            
        h, w = frame.shape[:2]
        
        contours, _ = detect_grains(
            frame,
            mode="auto",
            top_line_y=TOP_LINE_Y,
            bottom_line_y=BOTTOM_LINE_Y,
            bg_calibrator=bg_calibrator
        )

        centroids = []
        valid_contours = []
        for c in contours:
            M = cv2.moments(c)
            if M["m00"] > 0:
                centroids.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))
                valid_contours.append(c)
                
        _, new_indices = tracker.update(centroids)
        
        for di in new_indices:
            if di >= len(valid_contours): continue
            cnt = valid_contours[di]
            x, y, bw, bh = cv2.boundingRect(cnt)
            pad = 5
            x1 = max(x - pad, 0)
            y1 = max(y - pad, 0)
            x2 = min(x + bw + pad, w)
            y2 = min(y + bh + pad, h)
            
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                extracted.append(crop)
                
    cap.release()
    print(f"  -> Extracted {len(extracted)} grains from {video_path}")
    
    # Save to train (80%) or val (20%)
    for crop in extracted:
        split = TRAIN_DIR if random.random() < 0.8 else VAL_DIR
        out_path = os.path.join(split, cls_name, f"{uuid.uuid4().hex}.jpg")
        cv2.imwrite(out_path, crop)


if __name__ == "__main__":
    vids = ["newVids/black.mp4"]
    for vid in vids:
        basename = os.path.basename(vid).lower()
        if "sample_test" in basename:
            continue
            
        cls_name = None
        for c in CLASSES:
            if c in basename:
                cls_name = c
                break
                
        if cls_name:
            extract_video(vid, cls_name)
        else:
            print(f"Skipping {vid}, no matching class.")
            
    print("Extraction complete!")
