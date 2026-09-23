"""ffmpeg로 클립을 잘라내고 이어붙이는 공용 유틸리티."""
import os
import subprocess
import tempfile


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
        "-c:a",
        "aac",
        output_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
            output_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
