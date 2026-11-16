"""Fight event timeline contract.

Events are detections from 2D poses, not ground truth: a strike is an
*attempt*, a 2D overlap of the striking limb with the opponent is only a
*possible* contact, and knockdowns and takedowns are *possible* events
supported by the evidence listed in `measures`.

Since schema 1.11.0 a strike also carries an estimate of what it did: the
target zone, the outcome (landed / blocked / missed / unknown) with its own
confidence, whether it is a significant strike and the signals behind the
estimate (`evidence`). One camera and a 2D skeleton cannot make this certain:
`unknown` means it could not be told, never "missed". Damage signals
(`DamageSignal`) follow the ABC definition of damage and are estimates too.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, DataOrigin, VersionedContract
from .fighters import Fighter, FighterId
from .video import VideoInfo


class EventType(StrEnum):
    """Event categories. Adding a member is a minor schema version bump."""

    punch = "punch"
    kick = "kick"
    knee = "knee"
    elbow = "elbow"
    ground_strike = "ground_strike"  # strike from the top position on a grounded opponent
    clinch = "clinch"
    takedown = "takedown"
    ground_control = "ground_control"
    knockdown = "knockdown"
    stance_change = "stance_change"
    other = "other"


class Limb(StrEnum):
    left_hand = "left_hand"
    right_hand = "right_hand"
    left_foot = "left_foot"
    right_foot = "right_foot"
    left_knee = "left_knee"
    right_knee = "right_knee"


class TargetZone(StrEnum):
    """Where a strike was aimed: the opponent's zone the striking limb came closest to."""

    head = "head"
    body = "body"
    leg = "leg"


class StrikeOutcome(StrEnum):
    landed = "landed"  # reached the zone and the opponent reacted right after (head snap, push-back)
    blocked = "blocked"  # met the opponent's forearm or glove
    missed = "missed"  # came near no zone
    unknown = "unknown"  # could not be told (opponent not measured, or contact without a clear reaction)


class FightPhase(StrEnum):
    distance = "distance"
    clinch = "clinch"
    ground = "ground"


class EvidenceSignal(StrEnum):
    """What an estimate (strike outcome, damage signal, knockdown) rests on."""

    zone_contact = "zone_contact"  # the striking limb reached the target zone in 2D
    guard_contact = "guard_contact"  # it met the opponent's forearm or glove
    no_reach = "no_reach"  # it stayed away from every zone
    head_snap = "head_snap"  # the opponent's head moved suddenly against his shoulders right after
    body_push = "body_push"  # the opponent's torso was pushed along the strike
    leg_buckle = "leg_buckle"  # the struck leg was displaced
    target_unmeasured = "target_unmeasured"  # the opponent's zones or reaction could not be measured
    strike_before = "strike_before"  # a strike of the opponent shortly before (knockdown)
    hip_drop = "hip_drop"  # the hips went down to the floor
    base_change = "base_change"  # sudden change of the stance width
    knee_buckle = "knee_buckle"  # the hips dipped and came back
    unsteady_steps = "unsteady_steps"  # several quick steps
    hand_on_floor = "hand_on_floor"  # a glove at floor level while standing
    retreat = "retreat"  # moving away from the opponent
    no_offense = "no_offense"  # no attempt of his own in the following seconds
    pace_drop = "pace_drop"  # fewer attempts per measured minute for the rest of the round
    mobility_drop = "mobility_drop"  # less hand and foot activity for the rest of the round
    # whose it is was inferred: the other fighter is followed with high confidence
    identity_inferred = "identity_inferred"


class ImagePoint(Contract):
    """A point in analysis-video pixels."""

    x: float
    y: float


class FightEvent(Contract):
    event_id: str = Field(min_length=1)
    type: EventType
    actor: FighterId | None = Field(default=None, description="Fighter performing the action.")
    target: FighterId | None = Field(default=None, description="Fighter receiving the action.")
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0)
    peak_frame: int | None = Field(default=None, ge=0, description="Fastest moment of a strike / the fall.")
    peak_ms: float | None = Field(default=None, ge=0)
    limb: Limb | None = None
    possible_contact: bool = Field(
        default=False, description="The striking limb overlapped the opponent in 2D; contact is not certain.")
    location: ImagePoint | None = Field(default=None, description="Striking joint at the peak.")
    measures: dict[str, float] = Field(
        default_factory=dict, description="Measured values behind the detection (body units, seconds, cosines).")
    confidence: float = Field(ge=0, le=1, description="Detector confidence, not ground truth.")
    target_zone: TargetZone | None = Field(
        default=None, description="Strikes: the opponent's zone the limb came closest to. None: not measurable.")
    outcome: StrikeOutcome | None = Field(
        default=None, description="Strikes: estimated result. None: not a strike, or analysed before schema 1.11.0.")
    outcome_confidence: float | None = Field(
        default=None, ge=0, le=1, description="How sure the outcome is (None for unknown).")
    significant: bool | None = Field(
        default=None, description=(
            "Strikes: a significant strike (every strike at distance, power strikes in the clinch and on the "
            "ground). Says nothing about landing."))
    phase: FightPhase | None = Field(default=None, description="Strikes: where the fight was at the peak.")
    evidence: list[EvidenceSignal] = Field(default_factory=list, description="Signals behind the estimate.")
    attribution_confidence: float | None = Field(
        default=None, ge=0, le=1, description=(
            "How sure the identity of the fighter(s) is over the event's frames (the actor; both for an event "
            "without one). None: analysed before identities carried it."))
    attribution_uncertain: bool = Field(
        default=False, description="Below the attribution threshold: 'Kime ait belirsiz'. Not part of the momentum.")
    data_origin: DataOrigin
    note: str | None = None

    @model_validator(mode="after")
    def _ordered(self) -> FightEvent:
        if self.end_frame < self.start_frame or self.end_ms < self.start_ms:
            raise ValueError("event must not end before it starts")
        if self.peak_frame is not None and not self.start_frame <= self.peak_frame <= self.end_frame:
            raise ValueError("peak must lie inside the event")
        return self


class DamageType(StrEnum):
    """Damage signals, after the ABC definition of damage (2025 criteria)."""

    knockdown = "knockdown"  # down after a valid strike
    heavy_head_strike = "heavy_head_strike"  # landed head strike with a strong head snap
    wobble = "wobble"  # loss of balance after a landed strike
    forced_retreat = "forced_retreat"  # only backing off / defending after a landed strike
    output_drop = "output_drop"  # lasting drop of pace and mobility inside a round (cumulative)
    submission_danger = "submission_danger"  # held choke / joint lock with fading escapes
    visible_injury = "visible_injury"  # never detected: a flag set by the user


class DamageKind(StrEnum):
    immediate = "immediate"
    cumulative = "cumulative"


class DamageSignal(Contract):
    """A sign that a fighter was damaged. An estimate with its confidence, never a fact."""

    signal_id: str = Field(min_length=1)
    type: DamageType
    kind: DamageKind
    frame: int = Field(ge=0)
    time_ms: float = Field(ge=0)
    end_ms: float | None = Field(default=None, ge=0, description="Signals that last (retreat, output drop).")
    target_fighter: FighterId = Field(description="The fighter who was damaged.")
    by_fighter: FighterId = Field(description="The fighter credited with it (the opponent).")
    severity: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    attribution_confidence: float | None = Field(default=None, ge=0, le=1)
    attribution_uncertain: bool = False
    linked_event_id: str | None = Field(default=None, description="The strike or knockdown it comes from.")
    evidence: list[EvidenceSignal] = Field(default_factory=list)
    measures: dict[str, float] = Field(default_factory=dict)
    data_origin: DataOrigin
    note: str | None = None


class EventTimeline(VersionedContract):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    video: VideoInfo
    fighters: list[Fighter] = Field(max_length=2)
    events: list[FightEvent] = Field(default_factory=list)
    damage: list[DamageSignal] = Field(default_factory=list, description="Damage signals (schema 1.11.0 on).")
