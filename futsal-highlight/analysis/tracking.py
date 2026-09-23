"""YOLO로 공과 사람(선수) 위치를 함께 검출한다.

선수 개개인을 식별하거나 프레임 간 추적하지는 않는다 — 매 프레임 독립적으로
"공이 어디 있고 사람들이 어디 있는지"만 본다. 완벽한 선수 개인 식별(누가
누구인지)은 원거리 아마추어 영상에서 현재 기술로 안정적이지 않아 시도하지
않는다 — 이건 이전에 얼굴/신체 인식을 보류하기로 한 것과 같은 이유다.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

from highlight.object_detection import COCO_SPORTS_BALL_CLASS_ID

COCO_PERSON_CLASS_ID = 0


@dataclass
class FrameDetections:
    time_sec: float
    ball_center: tuple[float, float] | None
    person_centers: list[tuple[float, float]] = field(default_factory=list)
    frame_diagonal: float = 0.0


def detect_frame_objects(
    video_path: str,
    sample_fps: float = 5.0,
    model_name: str = "yolov8n.pt",
    conf_threshold: float = 0.25,
) -> list[FrameDetections]:
    """일정 간격으로 프레임을 샘플링해 공과 사람 위치를 검출한다."""
    from ultralytics import YOLO

    model = YOLO(model_name)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(int(round(source_fps / sample_fps)), 1)

    results_list: list[FrameDetections] = []
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
            person_centers: list[tuple[float, float]] = []

            for box in result.boxes:
                cls_id = int(box.cls[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                if cls_id == COCO_SPORTS_BALL_CLASS_ID:
                    conf = float(box.conf[0])
                    if conf > best_conf:
                        ball_center = center
                        best_conf = conf
                elif cls_id == COCO_PERSON_CLASS_ID:
                    person_centers.append(center)

            results_list.append(
                FrameDetections(
                    time_sec=frame_idx / source_fps,
                    ball_center=ball_center,
                    person_centers=person_centers,
                    frame_diagonal=diagonal,
                )
            )

        frame_idx += 1

    cap.release()
    return results_list
