"""오디오/모션 스파이크 탐지가 공유하는 신호 처리 유틸리티."""
import numpy as np

from .spike_event import SpikeEvent


def rolling_mean_std(x: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """중심 이동창 기준 평균/표준편차를 O(n)으로 계산한다 (경계는 가용 샘플만 사용)."""
    n = len(x)
    half = max(window // 2, 1)
    cumsum = np.concatenate([[0.0], np.cumsum(x)])
    cumsum_sq = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])

    idx = np.arange(n)
    lo = np.clip(idx - half, 0, n)
    hi = np.clip(idx + half + 1, 0, n)
    count = (hi - lo).astype(np.float64)

    window_sum = cumsum[hi] - cumsum[lo]
    window_sum_sq = cumsum_sq[hi] - cumsum_sq[lo]

    means = window_sum / count
    variance = np.maximum(window_sum_sq / count - means**2, 0.0)
    stds = np.sqrt(variance)
    return means, stds


def select_non_overlapping_peaks(
    candidate_idx: np.ndarray,
    scores: np.ndarray,
    times: np.ndarray,
    min_gap_sec: float,
) -> list[SpikeEvent]:
    """점수가 높은 순으로 그리디하게 골라, min_gap_sec 이내의 후보는 억제한다."""
    if len(candidate_idx) == 0:
        return []

    order = candidate_idx[np.argsort(-scores[candidate_idx])]
    selected_times: list[float] = []
    events: list[SpikeEvent] = []
    for idx in order:
        t = float(times[idx])
        if all(abs(t - st) >= min_gap_sec for st in selected_times):
            events.append(SpikeEvent(time_sec=t, score=float(scores[idx])))
            selected_times.append(t)

    events.sort(key=lambda e: e.time_sec)
    return events


def z_score_spikes(
    values: np.ndarray,
    times: np.ndarray,
    window: int,
    z_threshold: float,
    min_gap_sec: float,
    std_floor_ratio: float = 0.4,
) -> list[SpikeEvent]:
    """values 시계열에서 로컬 평균 대비 z_threshold 이상 튀는 지점들을 탐지한다.

    std_floor_ratio: 로컬 구간의 표본이 적어 표준편차 추정치가 우연히 아주
    작아지면(예: 잠깐 조용한 구간), 사소한 변동도 z-score가 크게 부풀려져
    오탐이 늘어난다. 이를 막기 위해 로컬 표준편차의 하한을
    (전체 트랙 표준편차 * std_floor_ratio)로 고정한다.
    """
    if len(values) == 0:
        return []
    means, stds = rolling_mean_std(values, window)
    global_std = float(np.std(values))
    stds = np.maximum(stds, std_floor_ratio * global_std)
    eps = 1e-8
    z_scores = (values - means) / (stds + eps)
    candidate_idx = np.where(z_scores >= z_threshold)[0]
    return select_non_overlapping_peaks(candidate_idx, z_scores, times, min_gap_sec)
