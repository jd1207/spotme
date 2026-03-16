from server.services.video_service import VideoService, validate_video

def test_validate_video_too_long():
    result = validate_video(duration_seconds=90, width=1920, height=1080)
    assert result["valid"] is False
    assert "60 seconds" in result["error"]

def test_validate_video_too_large():
    result = validate_video(duration_seconds=30, width=3840, height=2160)
    assert result["valid"] is False
    assert "1080p" in result["error"]

def test_validate_video_ok():
    result = validate_video(duration_seconds=30, width=1920, height=1080)
    assert result["valid"] is True

def test_extract_frames_command():
    service = VideoService(video_dir="/tmp/spotme_test_videos")
    cmd = service._build_ffmpeg_command("/tmp/test.mp4", "/tmp/frames", num_frames=3)
    assert "ffmpeg" in cmd[0]
