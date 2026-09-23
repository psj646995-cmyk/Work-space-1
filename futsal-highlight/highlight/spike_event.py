"""오디오/모션 분석에서 공통으로 쓰는 스파이크 이벤트 타입."""
from dataclasses import dataclass


@dataclass
class SpikeEvent:
    time_sec: float
    score: float  # 로컬 평균 대비 몇 표준편차만큼 튀었는지 (클수록 확실한 스파이크)
