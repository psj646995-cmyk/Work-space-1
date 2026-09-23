"""ffmpeg로 클립을 잘라내고 이어붙이는 공용 유틸리티."""
import os
import subprocess
import tempfile

# +faststart: moov atom을 파일 앞으로 옮겨서, 메신저 전송이나 스트리밍 재생 시
# 일부 플레이어가 "지원되지 않는 형식"으로 잘못 인식하는 문제를 막는다.
# yuv420p: 원본 영상의 픽셀 포맷이 흔치 않으면(예: 폰 카메라의 특수 색공간)
# 일부 재생기가 거부할 수 있어 가장 널리 지원되는 포맷으로 강제 변환한다.
_COMPAT_VIDEO_FLAGS = ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr_tail = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"ffmpeg 실행 실패 (명령: {' '.join(cmd)}):\n{stderr_tail}")


def extract_clip(
    video_path: str,
    center_time_sec: float,
    pre_seconds: float,
    post_seconds: float,
    output_path: str,
) -> None:
    start = max(0.0, center_time_sec - pre_seconds)
    duration = pre_seconds + post_seconds
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.2f}",
        "-i",
        video_path,
        "-t",
        f"{duration:.2f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        *_COMPAT_VIDEO_FLAGS,
        "-c:a",
        "aac",
        output_path,
    ]
    _run_ffmpeg(cmd)


def concat_clips(clip_paths: list[str], output_path: str) -> None:
    """여러 클립을 시간 순서대로 하나의 영상으로 이어붙인다.

    clip_paths의 모든 클립이 extract_clip으로 같은 설정(코덱/해상도)으로
    잘려나왔다는 전제 하에 재인코딩 없이(-c copy) 빠르게 이어붙인다.
    """
    if not clip_paths:
        raise ValueError("이어붙일 클립이 없습니다")

    with tempfile.TemporaryDirectory() as tmp_dir:
        list_path = os.path.join(tmp_dir, "concat_list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                escaped = os.path.abspath(clip_path).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]
        _run_ffmpeg(cmd)
