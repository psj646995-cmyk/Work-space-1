"""오디오 트랙에서 음량 급증(스파이크) 구간을 탐지한다.

골이 터지면 관중 함성/환호/휘슬 등으로 순간적으로 음량이 크게 튀는
경우가 많다는 가정에 기반한 신호 처리 휴리스틱이다. 사운드를 "함성"으로
분류하는 딥러닝 모델이 아니라 에너지(RMS) 기반 이상치 탐지이므로,
경기장 소음이나 마이크 상태에 따라 오탐/누락이 발생할 수 있다.
"""
import os
import subprocess
import tempfile

import librosa
import numpy as np

from .signal_utils import z_score_spikes
from .spike_event import SpikeEvent


def load_audio(path: str, sr: int = 22050) -> tuple[np.ndarray, int]:
    """영상/음원 파일의 오디오를 불러온다.

    librosa가 mp4 컨테이너를 직접 읽지 못하는 환경(특정 OS/라이브러리
    조합, 특히 Windows)이 있어서, ffmpeg로 오디오만 WAV로 먼저 뽑아낸
    뒤 그 WAV를 읽는다. 오디오 트랙이 아예 없는 영상(무음)이면 빈
    배열을 반환한다 — 그래도 모션/공속도 신호로는 계속 분석할 수 있다.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_path = os.path.join(tmp_dir, "audio.wav")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sr),
            wav_path,
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode != 0 or not os.path.exists(wav_path):
            return np.array([], dtype=np.float32), sr

        y, loaded_sr = librosa.load(wav_path, sr=sr, mono=True)
    return y, loaded_sr


def compute_rms_energy(
    y: np.ndarray, sr: int, frame_length: int = 2048, hop_length: int = 512
) -> tuple[np.ndarray, np.ndarray]:
    """RMS 에너지 시계열과 각 프레임의 타임스탬프(초)를 반환한다."""
    if len(y) == 0:
        return np.array([]), np.array([])
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
    if len(rms) == 0:
        return []
    frames_per_sec = sr / hop_length
    window = max(3, int(window_sec * frames_per_sec))
    return z_score_spikes(rms, times, window, z_threshold, min_gap_sec)
