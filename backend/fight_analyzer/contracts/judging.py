"""Round scoring under the Unified Rules of MMA (10-Point Must) by three virtual judges.

Everything here is an AI estimate from 2D video analysis, never an official
result. Round boundaries, the way the bout ended and point deductions cannot
be read reliably from the video, so they are entered by the user (MatchSetup)
and reported as such.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, DataOrigin, VersionedContract
from .events import EventType
from .fighters import Fighter, FighterId

DISCLAIMER = ("AI tahmini: 2B video analizinden üretilmiştir; resmi hakem kararı ya da resmi maç "
              "sonucu değildir.")


class FinishMethod(StrEnum):
    unknown = "unknown"  # not entered: the system does not guess how the bout ended
    decision = "decision"  # went the distance: the scorecards decide
    ko = "ko"
    tko = "tko"
    submission = "submission"
    disqualification = "disqualification"
    referee_stoppage = "referee_stoppage"  # incl. doctor / corner stoppage
    no_contest = "no_contest"


FINISHES = frozenset({FinishMethod.ko, FinishMethod.tko, FinishMethod.submission,
                      FinishMethod.disqualification, FinishMethod.referee_stoppage})


class RoundMark(Contract):
    """A round in the analysis video, marked by the user."""

    number: int = Field(ge=1, le=5)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0, description="Last frame of the round (inclusive).")

    @model_validator(mode="after")
    def _ordered(self) -> RoundMark:
        if self.end_frame < self.start_frame:
            raise ValueError("round must not end before it starts")
        return self


class PointDeduction(Contract):
    """A point taken by the referee (fouls cannot be detected from video: user input)."""

    round: int = Field(ge=1, le=5)
    fighter_id: FighterId
    points: int = Field(ge=1, le=2)
    note: str | None = Field(default=None, max_length=80)


class MatchEnding(Contract):
    """How the bout ended, as entered by the user (official information)."""

    method: FinishMethod = FinishMethod.unknown
    winner: FighterId | None = Field(default=None, description="Required for finishes and disqualifications.")
    round: int | None = Field(default=None, ge=1, le=5)
    time_s: float | None = Field(default=None, ge=0, le=600, description="Time into the final round.")

    @model_validator(mode="after")
    def _consistent(self) -> MatchEnding:
        if self.method in FINISHES and self.winner is None:
            raise ValueError("a finish needs the winning fighter")
        if self.method not in FINISHES and self.winner is not None:
            raise ValueError("only finishes name a winner; decisions are computed from the scorecards")
        return self


class MatchSetup(Contract):
    scheduled_rounds: int = Field(default=3, ge=1, le=5, description="3 for most bouts, 5 for title/main events.")
    round_length_s: float = Field(default=300, gt=0, le=600)
    rounds: list[RoundMark] = Field(default_factory=list, max_length=5,
                                    description="Empty: the whole video is treated as one unmarked round.")
    ending: MatchEnding = Field(default_factory=MatchEnding)
    deductions: list[PointDeduction] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _rounds(self) -> MatchSetup:
        numbers = [r.number for r in self.rounds]
        if len(set(numbers)) != len(numbers):
            raise ValueError("each round can be marked once")
        if any(n > self.scheduled_rounds for n in numbers):
            raise ValueError("round number beyond the scheduled rounds")
        ordered = sorted(self.rounds, key=lambda r: r.number)
        for a, b in zip(ordered, ordered[1:]):
            if b.start_frame <= a.end_frame:
                raise ValueError("rounds must be in order and must not overlap")
        if any(d.round > self.scheduled_rounds for d in self.deductions):
            raise ValueError("deduction in a round beyond the scheduled rounds")
        return self


class Criterion(StrEnum):
    """Unified Rules judging criteria in their order of priority."""

    effective_striking_grappling = "effective_striking_grappling"
    effective_aggressiveness = "effective_aggressiveness"  # only when the first is even
    cage_control = "cage_control"  # only when the first two are even


class ConfidenceLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class FighterRoundEvidence(Contract):
    """What the analysis measured for one fighter in one round (excluded parts left out)."""

    fighter_id: FighterId
    strike_attempts: int = Field(ge=0, description="Punch and knee attempts.")
    kick_attempts: int = Field(ge=0)
    possible_contact_strikes: int = Field(ge=0, description="Attempts whose limb overlapped the opponent in 2D.")
    possible_impact_strikes: int = Field(
        ge=0, description="Possible contact followed by the opponent's head snapping (sign of impact, unverified).")
    possible_knockdowns: int = Field(ge=0, description="Scored by this fighter, with enough evidence.")
    possible_takedowns: int = Field(ge=0)
    takedowns_to_control: int = Field(ge=0, description="Takedowns followed by top position.")
    control_s: float = Field(ge=0, description="Estimated top control on the ground.")
    advance_s: float = Field(ge=0)
    retreat_s: float = Field(ge=0)
    measured_s: float = Field(ge=0, description="Time this fighter could be measured.")
    identity_uncertain_s: float = Field(ge=0)
    uncertain_events: int = Field(ge=0, description="Possible knockdowns/takedowns below the evidence threshold.")


class KeyMoment(Contract):
    event_id: str
    time_s: float = Field(ge=0)
    fighter_id: FighterId | None
    type: EventType
    label: str
    confidence: float = Field(ge=0, le=1)
    uncertain: bool = True


class EdgeSummary(Contract):
    edge: FighterId | None = Field(description="Who had the advantage, if the evidence shows one.")
    text: str


class RoundAssessment(Contract):
    """Evidence and confidence of one round; the same for all judges."""

    number: int = Field(ge=1, le=5)
    marked: bool = Field(description="False: no rounds were marked and the whole video stands in for round 1.")
    start_frame: int
    end_frame: int
    start_s: float
    end_s: float
    recorded_s: float = Field(description="Fight time in the recording (excluded parts removed).")
    partial: bool = Field(description="Shorter than the scheduled round length.")
    scorable: bool = Field(description="Enough measured fight time to score the round.")
    unscorable_reason: str | None = None
    evidence: list[FighterRoundEvidence] = Field(min_length=2, max_length=2)
    key_moments: list[KeyMoment]
    damage: EdgeSummary
    grappling: EdgeSummary
    not_measured: list[str]
    confidence: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel
    confidence_notes: list[str]


class JudgeProfile(Contract):
    judge_id: str
    name: str
    description: str


class CriterionMargin(Contract):
    criterion: Criterion
    red: float
    blue: float
    decisive: bool = Field(description="The difference was large enough for this judge.")


class JudgeRoundScore(Contract):
    round: int
    scored: bool = Field(description="False: not enough data; the round is left out of the totals.")
    red: int = Field(ge=5, le=10)
    blue: int = Field(ge=5, le=10)
    winner: FighterId | None = Field(description="None: 10-10.")
    deciding_criterion: Criterion | None
    criteria: list[CriterionMargin]
    deductions: dict[str, int] = Field(default_factory=dict, description="fighter_id -> points taken this round.")
    reasons: list[str]


class JudgeScorecard(Contract):
    judge: JudgeProfile
    rounds: list[JudgeRoundScore]
    total_red: int
    total_blue: int
    winner: FighterId | None = Field(description="None: the card is a draw.")


class RoundSummary(Contract):
    """Round across the three judges."""

    number: int
    scored: bool
    red: int = Field(description="Most common red score among the judges.")
    blue: int
    winner: FighterId | None
    judges_agree: int = Field(ge=0, le=3, description="Judges that gave this winner (or 10-10).")
    reason: str
    confidence: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel


class DecisionType(StrEnum):
    unanimous = "unanimous"
    split = "split"
    majority = "majority"
    unanimous_draw = "unanimous_draw"
    majority_draw = "majority_draw"
    split_draw = "split_draw"


class VerdictStatus(StrEnum):
    decision = "decision"  # computed from the three AI scorecards
    finish = "finish"  # entered by the user; scorecards do not decide
    no_contest = "no_contest"
    not_computed = "not_computed"  # incomplete recording / unknown ending


class MatchVerdict(Contract):
    status: VerdictStatus
    method: FinishMethod
    decision_type: DecisionType | None
    winner: FighterId | None
    cards: list[str] = Field(description="Card totals, e.g. '29-28'.")
    summary: str
    reasons: list[str]
    source: str = Field(description="'ai_estimate' or 'user_input'.")
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_level: ConfidenceLevel | None = None
    notes: list[str]


class Scorecards(VersionedContract):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    ai_estimate: bool = Field(default=True, description="Always true: not an official result.")
    disclaimer: str = DISCLAIMER
    method: str
    fighters: list[Fighter]
    setup: MatchSetup
    rounds: list[RoundAssessment]
    round_summaries: list[RoundSummary]
    judges: list[JudgeScorecard] = Field(min_length=3, max_length=3)
    verdict: MatchVerdict
    warnings: list[str]
