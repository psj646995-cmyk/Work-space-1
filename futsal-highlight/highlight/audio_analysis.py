"""오디오 트랙에서 음량 급증(스파이크) 구간을 탐지한다.

골이 터지면 관중 함성/환호/휘슬 등으로 순간적으로 음량이 크게 튀는
경우가 많다는 가정에 기반한 신호 처리 휴리스틱이다. 사운드를 "함성"으로
분류하는 딥러닝 모델이 아니라 에너지(RMS) 기반 이상치 탐지이므로,
경기장 소음이나 마이크 상태에 따라 오탐/누락이 발생할 수 있다.
"""
import librosa
import numpy as np

from .signal_utils import z_score_spikes
from .spike_event import SpikeEvent


def load_audio(path: str, sr: int = 22050) -> tuple[np.ndarray, int]:
    y, loaded_sr = librosa.load(path, sr=sr, mono=True)
    return y, loaded_sr


def compute_rms_energy(
    y: np.ndarray, sr: int, frame_length: int = 2048, hop_length: int = 512
) -> tuple[np.ndarray, np.ndarray]:
    """RMS 에너지 시계열과 각 프레임의 타임스탬프(초)를 반환한다."""
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    return rms, times


def detect_audio_spikes(
    y: np.ndarray,
    sr: int,
    frame_length: int = 2048,
    hop_length: int = 512,
    window_sec: float = 15.0,
    z_threshold: float = 2.0,
    min_gap_sec: float = 8.0,
) -> list[SpikeEvent]:
    """음량이 로컬 평균 대비 z_threshold 표준편차 이상 튀는 시점들을 반환한다.

    window_sec: 스파이크 여부를 판단할 때 기준으로 삼는 주변 구간 길이(초).
    z_threshold: 이 값 이상 튀어야 후보로 인정 (값을 낮추면 더 많이 잡히지만 오탐 증가).
    min_gap_sec: 같은 사건이 여러 번 잡히지 않도록 후보 간 최소 시간 간격.
    """
    rms, times = compute_rms_energy(y, sr, frame_length, hop_length)
    frames_per_sec = sr / hop_length
    window = max(3, int(window_sec * frames_per_sec))
    return z_score_spikes(rms, times, window, z_threshold, min_gap_sec)
