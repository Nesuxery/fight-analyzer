"""Motion signals, event statistics and the experimental momentum model.

Units: lengths in torso lengths ("body units", mid-shoulders to mid-hips of
the same fighter), speeds in body units per second, times in milliseconds of
the analysis video. Signals are sampled on a fixed time grid (`sample_ms`);
a `None` sample means "no valid measurement" (fighter not verified, joints
not reliable, camera motion unknown) and is never filled with a guess.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, DataOrigin, VersionedContract
from .fighters import FighterId


class Posture(StrEnum):
    standing = "standing"
    grounded = "grounded"  # lying, sitting or on hands and knees
    transition = "transition"


class Movement(StrEnum):
    advancing = "advancing"  # moving toward the opponent
    retreating = "retreating"
    neutral = "neutral"


class GrapplingState(StrEnum):
    """Where the fight is, frame by frame (motion/grappling.py). An estimate from 2D joints;
    a frame on which a fighter is not measured has no state (null), never a guessed one."""

    distance = "distance"  # both on their feet, apart
    clinch = "clinch"  # both on their feet, tied up
    ground_red_top = "ground_red_top"  # on the ground, red (fighter_a) above blue
    ground_blue_top = "ground_blue_top"  # on the ground, blue (fighter_b) above red
    scramble = "scramble"  # on the ground (one or both), no clear top
    tied_up = "tied_up"  # hidden-opponent estimate only: tied up, standing or on the ground (not told apart)


class FighterSignals(Contract):
    fighter_id: FighterId
    valid: list[bool] = Field(description="Fighter verified with usable joints at the sample.")
    activity: list[float | None] = Field(description="Hand and foot motion relative to the body, 0..1.")
    hand_speed: list[float | None] = Field(description="Wrists relative to the hips, body units/s.")
    foot_speed: list[float | None] = Field(description="Ankles relative to the hips, body units/s.")
    approach_speed: list[float | None] = Field(
        description="Hip centre toward (+) / away from (-) the opponent, camera motion removed, body units/s.")
    movement: list[Movement | None]
    posture: list[Posture | None]
    facing_away: list[bool | None] = Field(
        default_factory=list, description=(
            "Back to the camera on most frames of the sample (nose and eyes not measured while both shoulders "
            "are). How well his strikes can be seen depends on it. Empty: analysed before events version 5."))
    wrists_measured: list[float | None] = Field(
        default_factory=list, description="Share of the sample's frames on which his wrists are measured, 0..1.")


class MotionTimeline(VersionedContract):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    sample_hz: float = Field(gt=0)
    sample_ms: list[float]
    camera_known: list[bool] = Field(description="Camera motion could be estimated from the background.")
    distance: list[float | None] = Field(description="Distance between the fighters' hip centres, body units.")
    phase: list[GrapplingState | None] = Field(
        default_factory=list, description=(
            "Grappling state at the sample (most of its frames; null: not measured). Empty: analysed before "
            "events version 5."))
    phase_hidden: list[GrapplingState | None] = Field(
        default_factory=list, description=(
            "Hidden-opponent estimate at the sample where `phase` is not measured (gizli rakip çıkarımı: one "
            "fighter unmeasured, the two estimated to be tied up): tied_up (standing or on the ground, not told "
            "apart), or the state measured right before and after when both are the same tied-up state. An "
            "inference with low confidence, never a measurement. Empty: analysed before events version 6."))
    fighters: list[FighterSignals] = Field(max_length=2)


class ExclusionReason(StrEnum):
    replay = "replay"  # broadcast replay
    slow_motion = "slow_motion"
    break_ = "break"  # outside the rounds: between rounds, corner footage, graphics
    intro = "intro"  # before the first round (walkouts, introductions)
    post_fight = "post_fight"  # after the bout ended
    stoppage = "stoppage"  # the fight clock stood still inside a round
    timeout = "timeout"  # inside a round: the scorebug away while the clock stands still, no sign of a replay
    other = "other"


class ExclusionSource(StrEnum):
    manual = "manual"  # marked by the user
    auto = "auto"  # found by the analysis; the user can turn it off with one click


class ExclusionSignal(StrEnum):
    """What an automatic excluded part rests on."""

    outside_rounds = "outside_rounds"  # lies outside the rounds in effect (Job.rounds)
    scorebug_missing = "scorebug_missing"  # the scorebug is not on screen
    replay_label = "replay_label"  # a replay label ("REPLAY"...) was read on screen
    clock_stopped = "clock_stopped"  # the fight clock is known to stand still
    wipe = "wipe"  # logo transition at its start or end
    slow_motion = "slow_motion"  # joint speeds well below the live level


class ExcludedSegment(Contract):
    """Part of the video that is not live fight time: marked by the user, or found
    automatically (replays, stoppages, everything outside the rounds).

    An excluded part is not fight time: events whose moment (peak frame, else start
    frame) lies in it are listed but neither counted nor scored, time-based points
    (advancing, control) and measured time do not accrue in it, and the momentum
    holds its value through it (decay runs on fight time)."""

    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0, description="Last excluded frame (inclusive).")
    reason: ExclusionReason = ExclusionReason.replay
    note: str | None = Field(default=None, max_length=80)
    source: ExclusionSource = ExclusionSource.manual
    auto_id: str | None = Field(default=None, max_length=60, description="Automatic parts: id used to turn it off.")
    confidence: float | None = Field(default=None, ge=0, le=1, description="Automatic parts only.")
    signals: list[ExclusionSignal] = Field(default_factory=list, description="Automatic parts: the evidence.")

    @model_validator(mode="after")
    def _ordered(self) -> ExcludedSegment:
        if self.end_frame < self.start_frame:
            raise ValueError("end_frame must not be before start_frame")
        return self


class AutoExclusion(ExcludedSegment):
    """An automatic excluded part and whether the user turned it off ("Geri al")."""

    dismissed: bool = Field(default=False, description="Turned off by the user: not applied.")


class SegmentExclusions(Contract):
    """Request body: the complete list of the user's excluded parts (replaces the previous one)."""

    segments: list[ExcludedSegment] = Field(default_factory=list, max_length=100)


class AutoExclusionEdits(Contract):
    """Request body of PUT /jobs/{id}/exclusions/auto: the automatic parts the user turned
    off, by auto_id (the complete list; the others apply)."""

    dismissed: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(default_factory=list, max_length=200)


class MomentumSource(StrEnum):
    strike_attempt = "strike_attempt"  # punch, knee, elbow or ground strike
    kick_attempt = "kick_attempt"
    contact_bonus = "contact_bonus"  # possible contact of an attempt
    advance = "advance"  # time spent moving toward the opponent
    control = "control"  # estimated ground control time
    knockdown = "knockdown"  # possible knockdown with enough evidence
    takedown = "takedown"  # possible takedown with enough evidence


class MomentumContribution(Contract):
    """One entry of the momentum ledger: where points came from."""

    contribution_id: str = Field(min_length=1)
    fighter_id: FighterId
    source: MomentumSource
    event_id: str | None = Field(default=None, description="Event the points come from, if any.")
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0, description="Equals start_ms for one-off points.")
    quantity: float = Field(ge=0, description="1 per attempt/event, seconds for time-based sources.")
    points: float = Field(ge=0, description="Points before decay (weight x quantity).")


class MomentumParameters(Contract):
    """Starting design parameters of the experimental model (not validated weights)."""

    half_life_s: float = Field(gt=0)
    prior: float = Field(ge=0, description="Added to both sides; 4 gives 50/50 without data.")
    strike_attempt: float = Field(ge=0)
    kick_attempt: float = Field(ge=0)
    contact_bonus: float = Field(ge=0)
    advance_per_s: float = Field(ge=0)
    control_per_s: float = Field(ge=0)
    knockdown: float = Field(ge=0)
    takedown: float = Field(ge=0)
    min_major_confidence: float = Field(ge=0, le=1)


class MomentumTimeline(VersionedContract):
    """Red share(t) = 100 x (m_red + prior) / (m_red + m_blue + 2 x prior); blue = 100 - red.
    m(t) = sum of ledger points, each halved every half_life_s seconds after it was earned."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    experimental: bool = Field(default=True, description="Experimental index, not a win probability.")
    parameters: MomentumParameters
    sample_hz: float = Field(gt=0)
    sample_ms: list[float]
    red_share: list[float] = Field(description="0..100; the blue share is 100 minus this.")
    m_red: list[float]
    m_blue: list[float]
    insufficient: list[bool] = Field(description="A fighter could not be measured at the sample.")
    contributions: list[MomentumContribution]
    exclusions: list[ExcludedSegment] = Field(
        default_factory=list, description="Excluded parts the ledger was computed with (already applied).")
    unattributed_event_ids: list[str] = Field(
        default_factory=list, description=(
            "Events left out of the ledger because it is uncertain whose they are (outside excluded parts)."))


class FighterEventCounts(Contract):
    fighter_id: FighterId
    strike_attempts: int = Field(ge=0, description="Punch, knee, elbow and ground strike attempts.")
    kick_attempts: int = Field(ge=0)
    possible_contacts: int = Field(ge=0)
    landed_strikes: int = Field(default=0, ge=0, description="Strikes estimated as landed (events version 4 on).")
    significant_attempts: int = Field(default=0, ge=0, description="Significant strike attempts.")
    significant_landed: int = Field(default=0, ge=0)
    possible_knockdowns: int = Field(ge=0, description="Knockdowns scored by this fighter.")
    possible_takedowns: int = Field(ge=0, description="Takedowns landed by this fighter (brief ones included).")
    takedown_attempts: int = Field(
        default=0, ge=0, description="Takedown attempts, landed ones included (events version 5 on).")
    brief_takedowns: int = Field(default=0, ge=0, description="Landed takedowns the opponent got up from at once.")
    reversals: int = Field(default=0, ge=0)
    get_ups: int = Field(default=0, ge=0)
    submission_attempts: int = Field(default=0, ge=0, description="Possible submission attempts (low confidence).")
    control_s: float = Field(ge=0, description="Estimated time on top on the ground.")
    clinch_control_s: float = Field(
        default=0, ge=0, description=(
            "Estimated clinch control: time in the clinch after this fighter drove the opponent back (low "
            "confidence; the cage is not measured)."))
    active_control_s: float = Field(
        default=0, ge=0, description="Control time (ground or clinch) during which he kept striking or threatening "
                                     "a submission.")
    advance_s: float = Field(ge=0)
    retreat_s: float = Field(ge=0)
    measured_s: float = Field(ge=0, description="Time with valid measurements of this fighter.")


class PhaseTimes(Contract):
    """Seconds of the video in each grappling state (whole video, before exclusions)."""

    distance_s: float = Field(ge=0)
    clinch_s: float = Field(ge=0)
    ground_s: float = Field(ge=0, description="On the ground with a clear top.")
    scramble_s: float = Field(ge=0)
    unknown_s: float = Field(ge=0, description="A fighter was not measured.")
    hidden_s: float = Field(
        default=0, ge=0, description=(
            "Part of unknown_s estimated as tied up while one fighter was not measured (gizli rakip çıkarımı; an "
            "inference, events version 6 on)."))


class EventsSummary(Contract):
    cache_key: str
    cache_hit: bool
    version: int = Field(default=0, ge=0, description="EVENTS_VERSION of the result (0: stored before it was kept).")
    method: str
    events: int = Field(ge=0)
    damage_signals: int = Field(default=0, ge=0)
    camera_known_share: float = Field(ge=0, le=1, description="Frames whose camera motion is known.")
    phases: PhaseTimes | None = Field(default=None, description="Grappling states (events version 5 on).")
    fighters: list[FighterEventCounts] = Field(max_length=2)


class ScoringSummary(Contract):
    cache_key: str
    cache_hit: bool
    parameters: MomentumParameters
    exclusions: list[ExcludedSegment] = Field(
        default_factory=list, description="Excluded parts applied: the user's and the automatic ones in effect, merged.")
    unattributed_events: int = Field(
        default=0, ge=0, description="Events left out because it is uncertain whose they are ('Kime ait belirsiz').")
    contributions: int = Field(ge=0)
    final_red_share: float = Field(ge=0, le=100)
