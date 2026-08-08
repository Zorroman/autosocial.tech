"""Long-form real-video-clips support: build_timeline() prefers clips over
photos per visual group (photos stay the required fallback), and
longform_render.render_video() dispatches each segment to the right
renderer (Ken-Burns for photos, straight scale+crop+trim for clips) --
both memory-safe, one source decoded at a time (see longform_render.py's
module docstring for why that matters on the 3.8 GB box).
"""
import subprocess

import pytest

import longform_pipeline as lp
import longform_render as lr
from app_settings import settings


class _Scene:
    def __init__(self, dur):
        self.estimated_duration = dur


def _groups(n):
    return [{"visual_group_id": f"g{i:02d}", "query": f"q{i}", "chapter_title": f"Глава {i+1}"}
            for i in range(n)]


def test_segment_defaults_to_photo_kind():
    seg = lr.Segment(image="x.jpg", seconds=5.0, motion="pan_left")
    assert seg.kind == "photo"
    assert seg.clip_start == 0.0


def test_build_timeline_photo_only_matches_old_behaviour():
    groups = _groups(2)
    group_photos = {"g00": ["p0.jpg", "p1.jpg"], "g01": ["p2.jpg", "p3.jpg"]}
    scenes = [_Scene(6.0) for _ in range(3)]
    segs = lp.build_timeline(scenes, groups, group_photos)
    assert segs  # non-empty
    assert all(s.kind == "photo" for s in segs)
    assert all(s.clip_start == 0.0 for s in segs)


def test_build_timeline_prefers_clips_over_photos_per_group():
    groups = _groups(1)
    group_photos = {"g00": ["photo_a.jpg", "photo_b.jpg"]}
    group_clips = {"g00": [("clip_a.mp4", 8.0), ("clip_b.mp4", 8.0)]}
    scenes = [_Scene(6.0) for _ in range(4)]  # ~24s of narration
    segs = lp.build_timeline(scenes, groups, group_photos, group_clips, seg_len=5.0)
    assert segs
    # clips come first in the group's own asset list -> round-robin picks them
    # before ever reaching the photos, as long as there's enough clip pool to
    # cover the early segments.
    assert segs[0].kind == "clip"
    assert segs[0].image in ("clip_a.mp4", "clip_b.mp4")


def test_build_timeline_never_exceeds_real_clip_duration():
    groups = _groups(1)
    group_photos = {"g00": []}
    group_clips = {"g00": [("short_clip.mp4", 3.0)]}  # shorter than seg_len=5.0
    scenes = [_Scene(6.0) for _ in range(3)]
    segs = lp.build_timeline(scenes, groups, group_photos, group_clips, seg_len=5.0)
    clip_segs = [s for s in segs if s.kind == "clip"]
    assert clip_segs
    assert all(s.seconds <= 3.0 + 1e-6 for s in clip_segs)


def test_build_timeline_falls_back_to_photo_when_group_has_no_clips():
    groups = _groups(1)
    group_photos = {"g00": ["photo_a.jpg"]}
    group_clips = {"g00": []}  # acquire_clips found nothing for this group
    scenes = [_Scene(6.0) for _ in range(2)]
    segs = lp.build_timeline(scenes, groups, group_photos, group_clips, seg_len=5.0)
    assert segs
    assert all(s.kind == "photo" for s in segs)
    assert all(s.image == "photo_a.jpg" for s in segs)


def test_build_timeline_never_repeats_same_asset_back_to_back():
    groups = _groups(1)
    group_photos = {"g00": []}
    group_clips = {"g00": [("clip_a.mp4", 20.0), ("clip_b.mp4", 20.0)]}
    scenes = [_Scene(6.0) for _ in range(6)]
    segs = lp.build_timeline(scenes, groups, group_photos, group_clips, seg_len=5.0)
    for a, b in zip(segs, segs[1:]):
        assert a.image != b.image


# --------------------------------------------------- real end-to-end render

def _ffmpeg(*args):
    subprocess.run([settings.FFMPEG_BIN, "-y", *args], check=True, capture_output=True)


@pytest.fixture(scope="module")
def mixed_sources(tmp_path_factory):
    d = tmp_path_factory.mktemp("lf_clip_fixtures")
    photo = d / "photo.jpg"
    _ffmpeg("-f", "lavfi", "-i", "color=c=0x224466:s=640x360", "-frames:v", "1", str(photo))
    clip = d / "clip.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=0x662244:s=640x360:d=4:r=25",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip))
    return {"photo": photo, "clip": clip}


def test_render_video_handles_mixed_photo_and_clip_segments(mixed_sources, tmp_path):
    prepped = tmp_path / "prepped.jpg"
    assert lr.prep_image(mixed_sources["photo"], prepped)

    segments = [
        lr.Segment(image=str(prepped), seconds=2.0, motion="pan_right", kind="photo"),
        lr.Segment(image=str(mixed_sources["clip"]), seconds=2.0, motion="pan_right", kind="clip"),
    ]
    out = tmp_path / "final_silent.mp4"
    result = lr.render_video(segments, out, tmp_path / "work", chunk_seconds=40)
    assert result["status"] == "succeeded", result
    assert out.exists() and out.stat().st_size > 10_000
    assert abs(result["duration"] - 4.0) < 0.5
