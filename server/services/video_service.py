from __future__ import annotations
import asyncio
import base64
import os

MAX_DURATION_SECONDS = 60
MAX_HEIGHT = 1080

def validate_video(duration_seconds, width, height):
    if duration_seconds > MAX_DURATION_SECONDS:
        return {"valid": False, "error": f"Video too long. Max {MAX_DURATION_SECONDS} seconds, got {duration_seconds:.0f}s."}
    if height > MAX_HEIGHT:
        return {"valid": False, "error": f"Resolution too high. Max 1080p, got {height}p."}
    return {"valid": True, "error": None}

class VideoService:
    def __init__(self, video_dir):
        self.video_dir = video_dir
        os.makedirs(video_dir, exist_ok=True)

    def _build_ffmpeg_command(self, video_path, output_dir, num_frames=3):
        return ["ffmpeg", "-i", video_path, "-vf", f"select='not(mod(n\\,30))',setpts=N/FRAME_RATE/TB", "-frames:v", str(num_frames), "-q:v", "2", os.path.join(output_dir, "frame_%03d.jpg")]

    async def extract_frames(self, video_path, num_frames=3):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = self._build_ffmpeg_command(video_path, tmpdir, num_frames)
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")
            frames_b64 = []
            for filename in sorted(os.listdir(tmpdir)):
                with open(os.path.join(tmpdir, filename), "rb") as f:
                    frames_b64.append(base64.b64encode(f.read()).decode())
            return frames_b64

    async def save_upload(self, file_bytes, filename):
        path = os.path.join(self.video_dir, filename)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return path
