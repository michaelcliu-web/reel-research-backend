"""Manim rendering and ffmpeg steps. All functions are blocking; call them via asyncio.to_thread."""
import os
import subprocess

from django.conf import settings


def media_path(*parts):
    return os.path.join(settings.MEDIA_ROOT, *parts)


def probe_duration(path, default):
    """Return the media file's duration in seconds, or `default` if ffprobe reports none."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip() or str(default))


def render_scene(code, pid, snum):
    scripts_dir = media_path("scripts")
    videos_dir = media_path("videos")
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)
    script_path = os.path.join(scripts_dir, f"{pid}_scene{snum}.py")
    with open(script_path, "w") as f:
        f.write(code)
    scene_video_path = os.path.join(videos_dir, f"{pid}_scene{snum}.mp4")
    result = subprocess.run(
        ["manim", "render", "--fps", "30", "-o", scene_video_path,
         script_path, "PaperScene"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise Exception(f"Scene {snum} render failed: {result.stderr[-500:]}")
    if not os.path.exists(scene_video_path):
        raise Exception(f"Scene {snum} video not found after render.")
    return scene_video_path


def merge_scene(video_path, aud_path, pid, snum, duration):
    """Loop the scene video under its narration audio, cut to the audio's length."""
    merged_path = media_path("videos", f"{pid}_scene{snum}_merged.mp4")
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", video_path,
            "-i", aud_path,
            "-t", str(duration),
            "-c:v", "libx264", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0",
            merged_path,
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise Exception(f"Scene {snum} merge failed: {result.stderr[-300:]}")
    return merged_path


def concat_scenes(paths, pid):
    """Join the merged scene clips; returns the final video's media URL."""
    videos_dir = media_path("videos")
    concat_list = os.path.join(videos_dir, f"{pid}_concat.txt")
    final_path = os.path.join(videos_dir, f"{pid}_final.mp4")
    with open(concat_list, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", concat_list, "-c", "copy", final_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise Exception(f"Concat failed: {result.stderr[-300:]}")
    os.remove(concat_list)
    return f"/media/videos/{pid}_final.mp4"


def ensure_thumbnail(pid, video_url):
    """Grab a mid-video frame as the thumbnail if missing; returns its URL or "" if unavailable."""
    thumbs_dir = media_path("thumbnails")
    os.makedirs(thumbs_dir, exist_ok=True)
    thumb_path = os.path.join(thumbs_dir, f"{pid}.jpg")

    if not os.path.exists(thumb_path) and video_url:
        video_file = media_path("videos", os.path.basename(video_url))
        if os.path.exists(video_file):
            try:
                seek_to = probe_duration(video_file, 20) * 0.5
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(seek_to),
                     "-i", video_file, "-frames:v", "1",
                     "-q:v", "2", thumb_path],
                    capture_output=True, text=True, timeout=15,
                )
            except Exception:
                return ""

    return f"/media/thumbnails/{pid}.jpg" if os.path.exists(thumb_path) else ""
