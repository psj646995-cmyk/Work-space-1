"""YOLO로 공을 검출해, 공이 급격히 빨라지는(강슛 후보) 구간을 탐지한다.

오디오/모션 스파이크는 화면 전체나 소리 전체를 보는 거친 신호라 슈팅처럼
작고 순식간에 일어나는 동작을 놓치기 쉽다. 이 모듈은 사전학습된 YOLOv8
(COCO 데이터셋, "sports ball" 클래스)로 공의 위치를 직접 추적해, 공의
이동 속도가 급증하는 순간을 더 정확한 신호로 잡는다.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from .signal_utils import z_score_spikes
from .spike_event import SpikeEvent

COCO_SPORTS_BALL_CLASS_ID = 32


@dataclass
class BallDetection:
    time_sec: float
    ball_center: tuple[float, float] | None  # 픽셀 좌표 (x, y), 검출 실패 시 None
    frame_diagonal: float  # 화면 대각선 픽셀 길이 (속도 정규화용)


def detect_ball_positions(
    video_path: str,
    sample_fps: float = 10.0,
    model_name: str = "yolov8n.pt",
    conf_threshold: float = 0.25,
) -> list[BallDetection]:
    """일정 간격으로 프레임을 샘플링해 각 프레임에서 공의 위치를 검출한다."""
    from ultralytics import YOLO  # 무거운 임포트라 실제로 쓸 때만 로드

    model = YOLO(model_name)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(int(round(source_fps / sample_fps)), 1)

    detections: list[BallDetection] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            height, width = frame.shape[:2]
            diagonal = float(np.hypot(width, height))

            result = model.predict(frame, verbose=False, conf=conf_threshold)[0]
            ball_center = None
            best_conf = -1.0
            for box in result.boxes:
                if int(box.cls[0]) != COCO_SPORTS_BALL_CLASS_ID:
                    continue
                conf = float(box.conf[0])
                if conf > best_conf:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    ball_center = ((x1 + x2) / 2, (y1 + y2) / 2)
                    best_conf = conf

            detections.append(
                BallDetection(
                    time_sec=frame_idx / source_fps,
                    ball_center=ball_center,
                    frame_diagonal=diagonal,
                )
            )

        frame_idx += 1

    cap.release()
    return detections


def compute_ball_speed_series(detections: list[BallDetection]) -> tuple[np.ndarray, np.ndarray]:
    """연속으로 공이 검출된 프레임 사이의 속도(화면 대각선 대비 초당 이동 비율)를 계산한다.

    공을 놓친 프레임(가려짐, 화면 밖 등)이 있으면 그 앞뒤는 연결하지 않고 건너뛴다.
    """
    speeds: list[float] = []
    times: list[float] = []
    prev_center: tuple[float, float] | None = None
    prev_time: float | None = None

    for d in detections:
        if d.ball_center is None:
            prev_center = None
            prev_time = None
            continue

        if prev_center is not None:
            dt = d.time_sec - prev_time
            if dt > 0:
                dx = d.ball_center[0] - prev_center[0]
                dy = d.ball_center[1] - prev_center[1]
                distance = float(np.hypot(dx, dy))
                speeds.append((distance / d.frame_diagonal) / dt)
                times.append(d.time_sec)

        prev_center = d.ball_center
        prev_time = d.time_sec

    return np.array(speeds), np.array(times)


def detect_ball_speed_spikes_from_series(
    speeds: np.ndarray,
    times: np.ndarray,
    sample_fps: float = 10.0,
    window_sec: float = 6.0,
    z_threshold: float = 2.0,
    min_gap_sec: float = 3.0,
) -> list[SpikeEvent]:
    """이미 계산된 공 속도 시계열에서 스파이크를 찾는다 (테스트/재사용 편의용)."""
    window = max(3, int(window_sec * sample_fps))
    return z_score_spikes(speeds, times, window, z_threshold, min_gap_sec)


def detect_ball_speed_spikes(
    video_path: str,
    sample_fps: float = 10.0,
    model_name: str = "yolov8n.pt",
    window_sec: float = 6.0,
    z_threshold: float = 2.0,
    min_gap_sec: float = 3.0,
) -> list[SpikeEvent]:
    """영상에서 공을 검출하고, 공 속도가 급증하는 구간(강슛 후보)을 반환한다."""
    detections = detect_ball_positions(video_path, sample_fps, model_name)
    speeds, times = compute_ball_speed_series(detections)
    return detect_ball_speed_spikes_from_series(
        speeds, times, sample_fps, window_sec, z_threshold, min_gap_sec
    )
