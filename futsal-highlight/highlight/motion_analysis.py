"""영상에서 화면 전체의 움직임이 급격히 커지는(스파이크) 구간을 탐지한다.

골이 들어가면 선수들이 몰려들거나 세리머니를 하며 화면 내 움직임이
급격히 늘어나는 경우가 많다는 가정에 기반한 휴리스틱이다. 사람/공을
검출하는 것이 아니라 옵티컬 플로우로 화면 전체의 평균 움직임 크기만
보므로, 카메라 흔들림이나 관중 이동에도 반응할 수 있다.
"""
import cv2
import numpy as np

from .signal_utils import z_score_spikes
from .spike_event import SpikeEvent


def compute_motion_magnitude_series(
    video_path: str,
    sample_fps: float = 5.0,
    resize_width: int = 320,
) -> tuple[np.ndarray, np.ndarray]:
    """일정 간격으로 프레임을 샘플링해 옵티컬 플로우 평균 크기 시계열을 계산한다.

    sample_fps: 초당 몇 프레임을 분석할지 (낮출수록 빠르지만 짧은 장면을 놓칠 수 있음).
    resize_width: 연산 속도를 위해 프레임을 이 너비로 축소.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(int(round(source_fps / sample_fps)), 1)

    magnitudes: list[float] = []
    times: list[float] = []
    prev_gray = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if resize_width and gray.shape[1] > resize_width:
                scale = resize_width / gray.shape[1]
                new_size = (resize_width, int(gray.shape[0] * scale))
                gray = cv2.resize(gray, new_size)

            if prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
                magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                magnitudes.append(float(magnitude.mean()))
                times.append(frame_idx / source_fps)

            prev_gray = gray

        frame_idx += 1

    cap.release()
    return np.array(magnitudes), np.array(times)


def detect_motion_spikes(
    video_path: str,
    sample_fps: float = 5.0,
    resize_width: int = 320,
    window_sec: float = 6.0,
    z_threshold: float = 2.0,
    min_gap_sec: float = 8.0,
) -> list[SpikeEvent]:
    """움직임 크기가 로컬 평균 대비 z_threshold 이상 튀는 시점들을 반환한다."""
    magnitudes, times = compute_motion_magnitude_series(video_path, sample_fps, resize_width)
    window = max(3, int(window_sec * sample_fps))
    return z_score_spikes(magnitudes, times, window, z_threshold, min_gap_sec)


def detect_motion_spikes_from_series(
    magnitudes: np.ndarray,
    times: np.ndarray,
    sample_fps: float = 5.0,
    window_sec: float = 6.0,
    z_threshold: float = 2.0,
    min_gap_sec: float = 8.0,
) -> list[SpikeEvent]:
    """이미 계산된 움직임 크기 시계열에서 스파이크를 찾는다 (테스트/재사용 편의용)."""
    window = max(3, int(window_sec * sample_fps))
    return z_score_spikes(magnitudes, times, window, z_threshold, min_gap_sec)
