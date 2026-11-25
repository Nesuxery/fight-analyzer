"""Runtime settings, read from FA_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DevicePreference = Literal["auto", "cpu", "cuda"]

ACCEPTED_EXTENSIONS: tuple[str, ...] = ("mp4", "mov", "m4v", "mkv", "webm", "avi")


@dataclass(frozen=True)
class UploadLimitSettings:
    max_bytes: int = 8 * 1024**3
    min_duration_s: float = 0.5
    max_duration_s: float = 3600.0
    # Limits on the displayed (rotation-corrected) size of the source.
    max_long_side: int = 3840
    max_short_side: int = 2160
    min_short_side: int = 144


@dataclass(frozen=True)
class TranscodeSettings:
    """Browser-playable constant-frame-rate analysis copy (H.264 + AAC MP4)."""

    max_short_side: int = 1080
    max_fps: float = 30.0
    crf: int = 20
    preset: str = "veryfast"
    audio_bitrate_k: int = 128


@dataclass(frozen=True)
class PoseSettings:
    imgsz: int = 640
    conf: float = 0.25
    iou: float = 0.7
    max_det: int = 20
    batch: int = 4
    # Seconds between preview frames sent to the UI while pose runs.
    preview_interval_s: float = 1.5


@dataclass(frozen=True)
class TrackingSettings:
    """Shot detection, short-term tracking and identity assignment.
    All values are part of the tracking cache keys."""

    tracker: str = "ocsort"  # Ultralytics tracker config used inside each shot
    # Camera cuts: 1 - Bhattacharyya distance of consecutive frame colour histograms.
    cut_threshold: float = 0.5
    cut_relative: float = 4.0  # ... or this many times the local median, if >= cut_floor
    # Low on purpose: in octagon broadcasts both shots are mostly the same canvas, so a
    # hard cut can move the colour histogram only ~0.2 (camera motion stays ~10x lower).
    cut_floor: float = 0.12
    min_shot_frames: int = 6
    # Detections whose boxes overlap this much are "in contact" (clinch, crossing, referee between).
    contact_iou: float = 0.15
    contact_cover: float = 0.45
    split_gap_frames: int = 3
    # Identity
    short_gap_s: float = 1.0  # occlusion kept as "occluded" before it becomes "uncertain"
    motion_gap_s: float = 1.0  # beyond this gap, position/motion is not used
    accept: float = 0.58
    accept_after_cut: float = 0.64
    margin: float = 0.08
    min_similarity: float = 0.45
    update_confidence: float = 0.75
    candidates: int = 8


@dataclass(frozen=True)
class IdentitySettings:
    """Identity layer on top of the tracking preparation (tracking/identity.py, quality.py).
    Kept apart from TrackingSettings on purpose: every field there is part of the
    preparation cache key. These are part of the identity cache key only. Starting
    design values, tuned on one sample broadcast."""

    # Camera cuts the preparation missed (two shots of the same canvas change the colour
    # histogram little): an isolated peak of the frame-to-frame colour change.
    extra_cut_floor: float = 0.03  # the usual change is ~0.004, the 99th percentile ~0.01
    extra_cut_relative: float = 6.0  # times the median change around the frame
    extra_cut_isolation: float = 0.5  # a neighbour frame this close to the peak: flash or wipe, not a cut
    # Appearance model: samples of each fighter from confident stretches all over the video.
    # per fighter, spread over the video; a short video gives fewer, and the model is used with
    # what there is (the summary reports how many)
    model_samples: int = 40
    model_min_confidence: float = 0.75
    model_min_weight: float = 4.0  # clean appearance evidence of a sampled stretch (summed quality)
    # Placing a fighter without a position: at least as much like the model as his least typical
    # sample is like the rest of them, less this.
    model_tolerance: float = 0.08
    # Third persons (referee, corner staff): seen next to both fighters for this many frames.
    third_min_frames: int = 5
    third_samples: int = 60
    # Inside an overlap a frame counts as verified when its own appearance says so.
    verify_margin: float = 0.08  # more like this fighter than like the other one or a third person
    verify_window_s: float = 1.0  # an unverified overlap frame this close to a verified one is "recent"
    confidence_verified: float = 0.9  # factors on the identity confidence inside overlaps
    confidence_recent: float = 0.75
    confidence_unverified: float = 0.45
    # A fighter placed from an overlapping box (after a cut or a long gap, by one frame's
    # appearance) keeps the unverified confidence until his own appearance is verified on
    # this many frames without an overlap.
    acquire_confirm_frames: int = 5
    # Data quality (quality.py): what lowers the confidence of a frame.
    far_height_share: float = 0.25  # fighter's box below this share of the frame height: far camera
    low_keypoint_conf: float = 0.5  # mean confidence of the body joints
    joint_min_conf: float = 0.5  # a joint below this is not a measurement (as MotionSettings.kp_min_conf)
    min_body_joints: int = 6  # of 12, needed for measurements (as in the motion stage)
    low_resolution_px: int = 110  # box height on a 1080-line frame
    blur_energy: float = 0.06  # mean gradient energy of shorts and torso below this: blurred


@dataclass(frozen=True)
class MotionSettings:
    """Motion signals and event detection. Lengths are in torso lengths ("body
    units", mid-shoulders to mid-hips), times in seconds: nothing depends on the
    frame rate. Part of the event cache key."""

    kp_min_conf: float = 0.5  # joints below this are not measurements
    max_gap_s: float = 0.15  # longer holes restart smoothing/velocity
    # One-Euro filter (time based): less smoothing the faster a joint moves.
    smooth_min_cutoff_hz: float = 2.0
    smooth_beta: float = 1.0  # cutoff increase per body unit/s of speed
    smooth_d_cutoff_hz: float = 4.0
    # Velocity = displacement over this much time (positions interpolated in time),
    # so a 30 fps and a 60 fps copy of the same motion give the same speeds.
    velocity_window_s: float = 0.067
    spike_body: float = 0.6  # one-frame jumps of this size are keypoint errors
    max_speed: float = 40.0  # body units/s; faster is a keypoint error, not motion
    activity_ref: float = 4.0  # limb speed counted as full activity
    # Strikes (speeds of the striking joint relative to the hips)
    strike_low: float = 3.0  # an attempt starts/ends where speed crosses this
    punch_peak: float = 6.0
    punch_extension: float = 0.55  # reach toward the opponent's upper body / arm length
    punch_extension_gain: float = 0.15
    punch_toward: float = 0.5  # cosine between motion and the direction to the opponent
    strike_max_distance: float = 3.5  # fighters' distance at the peak
    strike_max_duration_s: float = 1.0
    kick_peak: float = 6.0
    kick_extension: float = 0.7  # hip-ankle distance / leg length
    kick_raise: float = 0.5  # kicking ankle above the standing one
    kick_toward: float = 0.3
    knee_peak: float = 5.0
    knee_max_distance: float = 2.0
    same_motion_s: float = 0.12  # peaks of different limbs closer than this: one motion
    leg_over_punch_s: float = 0.25  # a kick/knee hides arm motion this close to it
    contact_reach: float = 0.5  # striking joint this close to an opponent joint (and inside the box)
    # Possible impact: after a possible contact the opponent's head moves this far (torso
    # lengths, relative to his shoulders, beyond his movement just before) within the window.
    impact_head_jolt: float = 0.3
    impact_window_s: float = 0.25
    # Whose event: mean identity confidence of the actor over the event's frames. Below this
    # the event is "Kime ait belirsiz" (listed and counted, but no momentum points).
    attribution_min: float = 0.5
    # Elbows: the elbow leads while the forearm stays folded, at close range.
    elbow_peak: float = 4.5
    elbow_fold: float = 0.55  # wrist to shoulder / arm length at the peak, at most
    elbow_toward: float = 0.4
    elbow_max_distance: float = 1.2
    # ... and drives toward the opponent: reaches this far from the shoulder toward his upper body
    # (upper-arm lengths), moves at least this fast relative to the wrist (raising the guard moves
    # the wrist much more than the elbow) and comes this close to his head or body zone (beyond
    # the zone's radius, torso lengths): a close-range strike.
    elbow_reach: float = 0.6
    elbow_lead: float = 0.8
    elbow_near: float = 0.35
    elbow_height: float = 0.2  # rises to at most this far below the shoulder line (covering up stays low)
    # Strikes from the top on a grounded opponent: no reach is needed, less speed.
    ground_strike_peak: float = 4.0
    ground_strike_toward: float = 0.3
    # Significant strikes: every strike at distance; in the clinch and on the ground only
    # power strikes, whose peak speed is this many times the attempt threshold.
    power_strength: float = 1.4
    # Target zones of the opponent and the striking surface (strikes.py), torso lengths.
    head_radius: float = 0.3
    body_radius: float = 0.3  # around the line from mid-shoulders to mid-hips
    leg_radius: float = 0.16
    guard_radius: float = 0.22  # around forearm and glove (a glove is big: ~0.2 torso lengths)
    fist_reach: float = 0.18  # the fist lies this far beyond the wrist, the foot beyond the ankle
    zone_reach: float = 0.1  # gap to a zone that still counts as reaching it (2D keypoint noise)
    miss_near: float = 0.3  # nearer than this to a zone or the guard, without reaching it: unknown, not missed
    miss_gap: float = 0.6  # this far from everything: missed with the highest confidence
    contact_before_s: float = 0.05  # the limb is followed from this long before the fastest moment
    contact_window_s: float = 0.2  # ... until this long after it
    # Reaction of the opponent within impact_window_s after the contact, needed for "landed".
    # Tuned on the sample broadcast (a tuning set): fighters move all the time, slipping moves the
    # head, stepping moves the legs, so only clear reactions count.
    head_snap_min: float = 0.15  # head against the shoulders along the strike, beyond his movement just before
    body_push_min: float = 3.0  # change of the torso velocity along the strike, torso lengths/s
    leg_buckle_min: float = 0.5  # the struck leg's knee or ankle against the hips
    # Arm motion that is not a punch: the fighter's own kick (legs moving fast and high), and the
    # hand going below the opponent's hips (catching or blocking a kick) while he stands.
    kick_motion: float = 0.8  # share of kick_peak that marks a kicking leg
    punch_below_hips: float = 0.15  # torso lengths below his hip centre
    block_reach: float = 0.6  # a hand this close to the kicking leg (his torso lengths) blocks the kick
    kick_merge_s: float = 0.3  # two stretches of one leg closer than this are one kick
    # Falls: the hips come down to this share of their height above the feet while standing.
    fall_upright: float = 1.3  # hips this far above the lower foot: a reference for standing
    fall_reference_s: float = 1.0  # standing time the reference is taken from
    fall_hold_s: float = 30.0  # the reference is kept this long after the fighter last stood
    fall_height_share: float = 0.65
    fall_close_s: float = 0.2  # shorter holes in "down" are closed
    # A fall right after strikes that all clearly missed (this sure) is a slip, not a knockdown.
    slip_missed_confidence: float = 0.6
    # Knockdown with an inferred identity: while one fighter is followed with at least this
    # confidence, the other person on the same tracker id just before / after the stretch in
    # which he is identified is taken to be the other fighter, for falls only.
    infer_min_confidence: float = 0.75
    infer_window_s: float = 1.5
    infer_max_gap_frames: int = 3
    inferred_confidence_cap: float = 0.4  # such a knockdown stays "possible" with low confidence
    infer_context_s: float = 4.0  # the inferred kinematics are computed this far around inferred frames
    # Damage signals (damage.py). Starting values, tuned on one broadcast.
    heavy_head_snap: float = 0.3  # along the strike
    knockdown_long_s: float = 2.0  # staying down this long makes a knockdown more severe
    wobble_window_s: float = 1.5  # after a landed strike
    wobble_base_change: float = 0.6  # stance width change within wobble_base_s
    wobble_base_s: float = 0.3
    wobble_dip: float = 0.3  # the hips dip by this share of their height and come back (punching dips ~0.15-0.3)
    wobble_steps: int = 3  # quick steps inside the window
    retreat_window_s: float = 2.5  # after a landed strike
    retreat_share: float = 0.6  # of the measured window spent moving away
    retreat_measured_share: float = 0.5  # of the window that must be measured
    # Movement and positions
    advance_speed: float = 0.5  # toward (+) / away (-) from the opponent
    advance_smooth_s: float = 0.3
    min_run_s: float = 0.4
    clinch_distance: float = 1.3
    clinch_min_s: float = 1.5
    control_distance: float = 1.8
    control_min_s: float = 1.0
    posture_stable_s: float = 0.4
    fall_max_s: float = 1.5  # standing -> down within this time is one fall
    knockdown_window_s: float = 1.2  # strike before a fall
    takedown_window_s: float = 2.0  # close contact before a fall
    sample_hz: float = 10.0  # resolution of the signal timelines sent to the UI
    # Camera motion from the background
    camera_width: int = 640
    camera_features: int = 400
    camera_min_inliers: int = 25


@dataclass(frozen=True)
class FeatureSettings:
    """What is derived from the cached events at request time, because it depends on the
    rounds and excluded parts, which the user can edit without processing again (not part
    of any cache key). Starting design values."""

    # Output drop (cumulative damage): after this many landed significant strikes, or one
    # knockdown / heavy head strike / wobble, the fighter's pace and mobility for the rest of
    # the round are compared with the part of the round before.
    output_drop_landed: int = 5
    output_drop_min_s: float = 45.0  # measured seconds needed before and after
    output_drop_pace: float = 0.35  # drop of attempts per measured minute
    output_drop_mobility: float = 0.2  # drop of the mean hand/foot activity
    output_drop_max_confidence: float = 0.4  # fatigue and tactics lower the output too


@dataclass(frozen=True)
class MomentumSettings:
    """Experimental momentum. Starting design parameters, not validated
    sport-science weights. Red share = 100 x (m1 + prior) / (m1 + m2 + 2 x prior)."""

    half_life_s: float = 20.0
    prior: float = 4.0
    strike_attempt: float = 1.0  # punch or knee
    kick_attempt: float = 1.3  # a kick is never also counted as a punch
    contact_bonus: float = 0.3  # "possible contact" on top of the attempt
    advance_per_s: float = 0.2
    control_per_s: float = 0.5
    knockdown: float = 4.0
    takedown: float = 2.5
    min_major_confidence: float = 0.5  # weaker major events are shown but add nothing


@dataclass(frozen=True)
class RulesetSettings:
    """Bout format of the ruleset. Commissions differ, so these are configuration,
    not code: ABC Unified Rules (2025 judging criteria clarification)."""

    name: str = "abc_2025"
    round_options: tuple[int, ...] = (3, 5)  # scheduled rounds the user can pick
    default_rounds: int = 3
    championship_rounds: int = 5  # title fights
    round_length_s: float = 300.0
    rest_s: float = 60.0
    # Clock lengths seen in broadcasts; a clock run is matched to the shortest one
    # that is not below its highest reading.
    standard_round_lengths_s: tuple[float, ...] = (120.0, 180.0, 240.0, 300.0)


@dataclass(frozen=True)
class BroadcastSettings:
    """Scorebug clock reading (OCR), round boundaries and round-break detection.
    Starting design values, tuned on the sample broadcast only."""

    sample_hz: float = 2.0  # band samples per second of video (scorebug presence)
    ocr_hz: float = 1.0  # clock reads per second of video, inside the clock area only
    roi_frames: int = 48  # frames spread over the video, searched for the clock area
    band_share: float = 0.24  # height share of the top and bottom bands searched
    min_text_px: int = 9  # text line height bounds, in pixels of a 1080-line frame
    max_text_px: int = 90
    min_presence: float = 0.2  # a scorebug text box is persistent in this share of frames
    min_clock_share: float = 0.5  # its reads that must parse as a clock
    min_read_conf: float = 0.6  # OCR confidence for a usable read
    min_round_conf: float = 0.3  # the short "R1" box reads with less confidence; numbers are voted per run
    run_tolerance_s: float = 2.0  # clock vs video time disagreement inside one run
    min_round_s: float = 20.0  # shorter clock runs are not rounds
    min_run_reads: int = 5
    start_snap_s: float = 6.0  # first running read this close to the top: the round started there
    end_snap_s: float = 3.0  # last read this close to 0:00: the round ran out
    max_interpolate_s: float = 12.0  # clock gaps longer than this stay unknown
    # Without a readable clock: a long quiet stretch with people sitting / many people in view.
    break_min_s: float = 45.0
    break_quiet_share: float = 0.6
    break_max_confidence: float = 0.5
    # ---- Replays, stoppages and non-fight parts (broadcast/replay.py) ----
    # Signal 1a, scorebug on screen: the strip around the clock compared with its usual look.
    bug_strip: float = 1.0  # strip = clock area widened by this many of its widths on each side
    bug_present: float = 0.5  # template match (zero-mean correlation) from which the scorebug counts as shown
    bug_min_frames: int = 3  # search frames with a readable clock needed to learn the strip
    # Signal 1b, replay label: words read in the top / bottom band while the clock does not advance
    # (compared in upper case without diacritics or punctuation).
    replay_words: tuple[str, ...] = ("REPLAY", "TEKRAR", "SLOW MO", "SLO MO", "SLOW MOTION", "AGIR CEKIM")
    label_max_boxes: int = 8  # text boxes read per frame, largest first
    label_min_reads: int = 2  # reads of a label inside a part for the signal
    # Signal 2, fight clock standing still: video time the clock lost between reads.
    stall_min_s: float = 3.0
    stall_share: float = 0.75  # share of the time between two reads that the clock must have lost
    # Signal 3, logo transition (wipe): many frames in a row that change a lot, or a very short shot.
    wipe_step: float = 0.03  # colour change to the previous frame (camera motion stays ~10x lower)
    wipe_window_s: float = 1.0
    wipe_min_s: float = 0.2  # of such frames inside the window
    wipe_max_shot_s: float = 1.5  # two cuts closer than this: the logo between them
    wipe_near_s: float = 1.5  # distance of a transition from the start / end of a part
    # Signal 4, slow motion: limb speed of the people in view against the live median.
    slow_ratio: float = 0.65  # half speed lands near 0.5; live stretches of 6 s and more rarely fall below this
    slow_min_s: float = 3.0  # measured time needed inside the part
    # Parts: at least two of the four signals make a replay.
    replay_min_s: float = 2.0
    replay_max_s: float = 90.0  # between two transitions (parts found without a scorebug)
    signal_share: float = 0.6  # of a part's samples that must show a signal
    close_gap_s: float = 1.5  # shorter holes in a signal are closed
    edge_share: float = 0.9  # before the first / after the last round: share without scorebug or running clock
    min_segment_s: float = 1.0
    replay_confidence: tuple[float, ...] = (0.6, 0.8, 0.9)  # with 2, 3 and 4 signals
    label_bonus: float = 0.05
    stoppage_confidence: float = 0.7
    edge_confidence: float = 0.6


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    device: DevicePreference = "auto"
    pose_model: str = "yolo26s-pose.pt"
    models_dir_override: Path | None = None
    worker_poll_interval_s: float = 1.0
    worker_heartbeat_interval_s: float = 2.0
    # Health reports the worker as unavailable after this long without a heartbeat.
    worker_stale_after_s: float = 10.0
    # A running job whose heartbeat is older than this is considered abandoned.
    job_stale_after_s: float = 30.0
    job_max_attempts: int = 2
    # Analyses waiting or running at the same time (uploads beyond this are refused).
    max_active_jobs: int = 20
    # Uploads need room for the source, the analysis copy and caches.
    min_free_disk_bytes: int = 2 * 1024**3
    upload: UploadLimitSettings = field(default_factory=UploadLimitSettings)
    transcode: TranscodeSettings = field(default_factory=TranscodeSettings)
    pose: PoseSettings = field(default_factory=PoseSettings)
    tracking: TrackingSettings = field(default_factory=TrackingSettings)
    identity: IdentitySettings = field(default_factory=IdentitySettings)
    motion: MotionSettings = field(default_factory=MotionSettings)
    features: FeatureSettings = field(default_factory=FeatureSettings)
    momentum: MomentumSettings = field(default_factory=MomentumSettings)
    ruleset: RulesetSettings = field(default_factory=RulesetSettings)
    broadcast: BroadcastSettings = field(default_factory=BroadcastSettings)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def jobs_dir(self) -> Path:
        """Per-job working files (live preview frames)."""
        return self.data_dir / "jobs"

    @property
    def uploads_dir(self) -> Path:
        """Original uploads, stored by content hash: uploads/<sha256>/source.<ext>."""
        return self.data_dir / "uploads"

    @property
    def cache_dir(self) -> Path:
        """Reusable results: cache/video/<key>/ and cache/pose/<key>/."""
        return self.data_dir / "cache"

    @property
    def models_dir(self) -> Path:
        return self.models_dir_override or self.data_dir / "models"

    @property
    def ultralytics_config_dir(self) -> Path:
        return self.data_dir / "ultralytics"

    @property
    def pose_model_path(self) -> Path:
        return self.models_dir / self.pose_model

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.jobs_dir, self.uploads_dir, self.cache_dir,
                  self.models_dir, self.ultralytics_config_dir):
            d.mkdir(parents=True, exist_ok=True)


def _num(env: os._Environ[str], name: str, default: float, cast=float):
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number (got {raw!r})") from None


def load_settings() -> Settings:
    env = os.environ
    device = env.get("FA_DEVICE", "auto").lower()
    if device not in ("auto", "cpu", "cuda"):
        raise ValueError(f"FA_DEVICE must be auto, cpu or cuda (got {device!r})")
    models_dir = env.get("FA_MODELS_DIR")
    up = UploadLimitSettings()
    tc = TranscodeSettings()
    ps = PoseSettings()
    return Settings(
        data_dir=Path(env.get("FA_DATA_DIR", PROJECT_ROOT / "data")).resolve(),
        api_host=env.get("FA_API_HOST", "127.0.0.1"),
        api_port=int(env.get("FA_API_PORT", "8000")),
        device=device,  # type: ignore[arg-type]
        pose_model=env.get("FA_POSE_MODEL", Settings.pose_model),
        max_active_jobs=_num(env, "FA_MAX_ACTIVE_JOBS", Settings.max_active_jobs, int),
        min_free_disk_bytes=int(_num(env, "FA_MIN_FREE_DISK_MB", Settings.min_free_disk_bytes / 1024**2) * 1024**2),
        models_dir_override=Path(models_dir).resolve() if models_dir else None,
        upload=UploadLimitSettings(
            max_bytes=int(_num(env, "FA_MAX_UPLOAD_MB", up.max_bytes / 1024**2) * 1024**2),
            min_duration_s=_num(env, "FA_MIN_DURATION_S", up.min_duration_s),
            max_duration_s=_num(env, "FA_MAX_DURATION_S", up.max_duration_s),
            max_long_side=_num(env, "FA_MAX_LONG_SIDE", up.max_long_side, int),
            max_short_side=_num(env, "FA_MAX_SHORT_SIDE", up.max_short_side, int),
            min_short_side=_num(env, "FA_MIN_SHORT_SIDE", up.min_short_side, int),
        ),
        transcode=TranscodeSettings(
            max_short_side=_num(env, "FA_ANALYSIS_MAX_SHORT_SIDE", tc.max_short_side, int),
            max_fps=_num(env, "FA_ANALYSIS_MAX_FPS", tc.max_fps),
            crf=tc.crf,
            preset=tc.preset,
            audio_bitrate_k=tc.audio_bitrate_k,
        ),
        pose=PoseSettings(
            imgsz=_num(env, "FA_POSE_IMGSZ", ps.imgsz, int),
            conf=_num(env, "FA_POSE_CONF", ps.conf),
            iou=ps.iou,
            max_det=_num(env, "FA_POSE_MAX_DET", ps.max_det, int),
            batch=_num(env, "FA_POSE_BATCH", ps.batch, int),
            preview_interval_s=ps.preview_interval_s,
        ),
    )


def apply_runtime_env(settings: Settings) -> None:
    """Keep third-party libraries local and safe: Ultralytics settings live in
    the data dir, its online features (telemetry, auto-downloads, update
    checks) are off, and checkpoints load with torch weights_only (no
    arbitrary pickle code). Must run before ultralytics is imported."""
    os.environ.setdefault("YOLO_CONFIG_DIR", str(settings.ultralytics_config_dir))
    os.environ.setdefault("YOLO_OFFLINE", "1")
    os.environ.setdefault("ULTRALYTICS_SAFE_LOAD", "1")
