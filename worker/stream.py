import cv2
from constants import URL

def connect_stream():
    cap = cv2.VideoCapture(URL, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def release_stream(cap):
    if cap is not None:
        cap.release()
    return None
