from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from fight_analyzer.config import TranscodeSettings
from fight_analyzer.contracts import SourceVideo
from fight_analyzer.fsutil import sha256_file
from fight_analyzer.media.analysis_video import load_cached, prepare, video_cache_key
from fight_analyzer.media.probe import ProbeError, check_decodable, parse_header, probe_video
from fight_analyzer.media.transcode import choose_frame_rate
from tests.support.media import make_rotated, make_video


def _source(path: Path) -> SourceVideo:
    p = probe_video(path)
    return SourceVideo(filename=path.name, size_bytes=path.stat().st_size, sha256=sha256_file(path),
                       width=p.width, height=p.height, fps=p.fps,
                       duration_ms=(p.duration_s or 0) * 1000, rotation_deg=p.rotation_deg,
                       has_audio=p.has_audio)


HEADER = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'phone.mp4':
  Duration: 00:01:02.50, start: 0.000000, bitrate: 1607 kb/s
  Stream #0:0[0x1](und): Video: hevc (Main) (hvc1 / 0x31637668), yuv420p(tv), 1920x1080, 9000 kb/s, SAR 1:1 DAR 16:9, 29.97 fps, 29.97 tbr, 90k tbn (default)
      Side data:
        displaymatrix: rotation of -90.00 degrees
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
"""


def test_parse_header_rotation_audio_and_duration():
    p = parse_header(HEADER)
    assert (p.codec, p.coded_width, p.coded_height) == ("hevc", 1920, 1080)
    assert p.rotation_deg == 90 and (p.width, p.height) == (1080, 1920)
    assert p.fps == 29.97 and p.duration_s == 62.5 and p.has_audio


@pytest.mark.parametrize("text, code", [
    ("garbage", "invalid_video"),
    ("Input #0, mp3, from 'a.mp3':\n  Stream #0:0: Audio: mp3, 44100 Hz", "no_video_stream"),
])
def test_parse_header_rejects(text, code):
    with pytest.raises(ProbeError) as err:
        parse_header(text)
    assert err.value.code == code


@pytest.mark.parametrize("source, expected", [
    (29.97, Fraction(30000, 1001)), (59.94, Fraction(30000, 1001)), (60, Fraction(30)),
    (50, Fraction(25)), (25, Fraction(25)), (23.98, Fraction(24000, 1001)), (120, Fraction(30)),
    (36.13, Fraction(30)), (15, Fraction(15)), (12.5, Fraction(25, 2)), (None, Fraction(30)),
])
def test_choose_frame_rate(source, expected):
    assert choose_frame_rate(source, 30) == expected


def test_probe_real_files(tmp_path):
    clip = make_video(tmp_path / "a.mp4", audio=True)
    p = probe_video(clip)
    assert (p.width, p.height, p.has_audio, p.rotation_deg) == (320, 180, True, 0)
    assert check_decodable(clip) >= 1
    rotated = probe_video(make_rotated(clip, tmp_path / "r.mp4", 90))
    assert (rotated.width, rotated.height) == (180, 320) and rotated.rotation_deg == 270


def test_renamed_or_truncated_files_are_rejected(tmp_path):
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"\x00\x01not a video" * 500)
    with pytest.raises(ProbeError):
        probe_video(fake)
    clip = make_video(tmp_path / "ok.mp4", seconds=2, extra_output=["-movflags", "+faststart"])
    truncated = tmp_path / "cut.mp4"
    truncated.write_bytes(clip.read_bytes()[:3000])
    with pytest.raises(ProbeError):
        probe_video(truncated)
        check_decodable(truncated)


def test_analysis_copy_rotation_cfr_audio_and_cache(tmp_path):
    clip = make_video(tmp_path / "src.mp4", seconds=2, rate="50", audio=True)
    rotated = make_rotated(clip, tmp_path / "rot.mp4", 90)
    cache = tmp_path / "cache"
    av = prepare(cache, rotated, _source(rotated), TranscodeSettings())
    v = av.video
    assert (v.width, v.height) == (180, 320)  # rotation applied, aspect kept
    assert (v.fps_num, v.fps_den) == (25, 1)  # 50 fps halved evenly, constant rate
    assert abs(v.frame_count - 50) <= 1 and v.has_audio
    assert probe_video(cache / "video" / av.cache_key / "analysis.mp4").rotation_deg == 0
    again = prepare(cache, rotated, _source(rotated), TranscodeSettings())
    assert again.cache_hit and again.sha256 == av.sha256
    assert video_cache_key(_source(rotated).sha256, TranscodeSettings(crf=23)) != av.cache_key


def test_odd_time_base_keeps_every_frame(tmp_path):
    # Social-media style huge time base; FFmpeg 7.1's scale filter used to
    # drop trailing frames when it ran before the fps filter.
    clip = make_video(tmp_path / "tb.mp4", seconds=3, rate="36",
                      extra_output=["-video_track_timescale", "359980000"])
    av = prepare(tmp_path / "cache", clip, _source(clip), TranscodeSettings())
    assert av.video.frame_count == 90  # the old filter order produced 89


def test_cancelled_transcode_leaves_no_cache_entry(tmp_path):
    clip = make_video(tmp_path / "src.mp4", seconds=4, size="640x360")
    cache = tmp_path / "cache"

    class Stop(Exception):
        pass

    def cancel(_t, _f):
        raise Stop

    with pytest.raises(Stop):
        prepare(cache, clip, _source(clip), TranscodeSettings(), cancel)
    key = video_cache_key(sha256_file(clip), TranscodeSettings())
    assert load_cached(cache, key) is None
    assert not any((cache / "video").iterdir())
