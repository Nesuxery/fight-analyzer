/* Generated from shared/schemas/fight-analyzer.v1.schema.json by `npm run gen:types`. Do not edit by hand. */

/**
 * Stable identity of the two fighters chosen by the user.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterId".
 */
export type FighterId = "fighter_a" | "fighter_b";
/**
 * Where analysis values come from. Demo data must never be shown as measured.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "DataOrigin".
 */
export type DataOrigin = "measured" | "demo";
/**
 * What an estimate (strike outcome, damage signal, knockdown) rests on.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "EvidenceSignal".
 */
export type EvidenceSignal =
  | "zone_contact"
  | "guard_contact"
  | "no_reach"
  | "head_snap"
  | "body_push"
  | "leg_buckle"
  | "target_unmeasured"
  | "strike_before"
  | "hip_drop"
  | "base_change"
  | "knee_buckle"
  | "unsteady_steps"
  | "hand_on_floor"
  | "retreat"
  | "no_offense"
  | "pace_drop"
  | "mobility_drop"
  | "identity_inferred"
  | "close_contact"
  | "level_change"
  | "top_position"
  | "position_change"
  | "neck_wrap"
  | "escape_fade";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "DamageKind".
 */
export type DamageKind = "immediate" | "cumulative";
/**
 * Damage signals, after the ABC definition of damage (2025 criteria).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "DamageType".
 */
export type DamageType =
  | "knockdown"
  | "heavy_head_strike"
  | "wobble"
  | "forced_retreat"
  | "output_drop"
  | "submission_danger"
  | "visible_injury";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Limb".
 */
export type Limb =
  "left_hand" | "right_hand" | "left_foot" | "right_foot" | "left_knee" | "right_knee";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "StrikeOutcome".
 */
export type StrikeOutcome = "landed" | "blocked" | "missed" | "unknown";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FightPhase".
 */
export type FightPhase = "distance" | "clinch" | "ground";
/**
 * Where a strike was aimed: the opponent's zone the striking limb came closest to.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TargetZone".
 */
export type TargetZone = "head" | "body" | "leg";
/**
 * Event categories. Adding a member is a minor schema version bump.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "EventType".
 */
export type EventType =
  | "punch"
  | "kick"
  | "knee"
  | "elbow"
  | "ground_strike"
  | "clinch"
  | "takedown"
  | "takedown_attempt"
  | "ground_control"
  | "reversal"
  | "get_up"
  | "submission_attempt"
  | "knockdown"
  | "stance_change"
  | "other";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExclusionReason".
 */
export type ExclusionReason =
  "replay" | "slow_motion" | "break" | "intro" | "post_fight" | "stoppage" | "timeout" | "other";
/**
 * What an automatic excluded part rests on.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExclusionSignal".
 */
export type ExclusionSignal =
  "outside_rounds" | "scorebug_missing" | "replay_label" | "clock_stopped" | "wipe" | "slow_motion";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExclusionSource".
 */
export type ExclusionSource = "manual" | "auto";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MomentumSource".
 */
export type MomentumSource =
  | "strike_attempt"
  | "kick_attempt"
  | "contact_bonus"
  | "advance"
  | "control"
  | "knockdown"
  | "takedown";
/**
 * Unified Rules judging criteria in their order of priority.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Criterion".
 */
export type Criterion =
  "effective_striking_grappling" | "effective_aggressiveness" | "cage_control";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ConfidenceLevel".
 */
export type ConfidenceLevel = "low" | "medium" | "high";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FinishMethod".
 */
export type FinishMethod =
  | "unknown"
  | "decision"
  | "ko"
  | "tko"
  | "submission"
  | "disqualification"
  | "referee_stoppage"
  | "no_contest";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "DecisionType".
 */
export type DecisionType =
  "unanimous" | "split" | "majority" | "unanimous_draw" | "majority_draw" | "split_draw";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "VerdictStatus".
 */
export type VerdictStatus = "decision" | "finish" | "no_contest" | "not_computed";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Ruleset".
 */
export type Ruleset = "abc_2025";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoiSource".
 */
export type RoiSource = "auto" | "manual";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundSource".
 */
export type RoundSource = "ocr" | "break" | "manual";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "CheckStatus".
 */
export type CheckStatus = "ok" | "degraded" | "unavailable";
/**
 * Analysis stages in execution order.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PipelineStage".
 */
export type PipelineStage =
  | "video_prep"
  | "pose"
  | "tracking_prep"
  | "broadcast"
  | "tracking"
  | "events"
  | "scoring"
  | "export";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JobType".
 */
export type JobType = "analysis" | "export";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "OutdatedReason".
 */
export type OutdatedReason =
  "broadcast_missing" | "broadcast_outdated" | "identity_outdated" | "events_outdated";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "BroadcastNoteCode".
 */
export type BroadcastNoteCode =
  | "ocr_unavailable"
  | "clock_not_found"
  | "roi_unreadable"
  | "no_rounds"
  | "round_number_inferred"
  | "rounds_from_breaks";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExportFileKind".
 */
export type ExportFileKind = "video" | "metrics" | "bundle";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "UncertainReason".
 */
export type UncertainReason = "camera_cut" | "overlap" | "lost" | "ambiguous" | "anchor_conflict";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ProgressUnit".
 */
export type ProgressUnit = "frames" | "seconds" | "bytes";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundNoteCode".
 */
export type RoundNoteCode = "auto_conflicts_manual" | "beyond_scheduled" | "out_of_order";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JobStatus".
 */
export type JobStatus =
  "queued" | "running" | "awaiting_selection" | "completed" | "failed" | "cancelled";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Movement".
 */
export type Movement = "advancing" | "retreating" | "neutral";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Posture".
 */
export type Posture = "standing" | "grounded" | "transition";
/**
 * Where the fight is, frame by frame (motion/grappling.py). An estimate from 2D joints;
 * a frame on which a fighter is not measured has no state (null), never a guessed one.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "GrapplingState".
 */
export type GrapplingState =
  "distance" | "clinch" | "ground_red_top" | "ground_blue_top" | "scramble";
/**
 * COCO-17 keypoints in model output order: index k of every keypoint list
 * is the k-th member below (0 = nose ... 16 = right_ankle). This is the
 * order predicted by the Ultralytics YOLO pose models (see
 * https://docs.ultralytics.com/tasks/pose/#keypoint-index-map).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "KeypointName".
 */
export type KeypointName =
  | "nose"
  | "left_eye"
  | "right_eye"
  | "left_ear"
  | "right_ear"
  | "left_shoulder"
  | "right_shoulder"
  | "left_elbow"
  | "right_elbow"
  | "left_wrist"
  | "right_wrist"
  | "left_hip"
  | "right_hip"
  | "left_knee"
  | "right_knee"
  | "left_ankle"
  | "right_ankle";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackState".
 */
export type TrackState = "tracked" | "occluded" | "uncertain";
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "SkeletonFormat".
 */
export type SkeletonFormat = "coco17";
/**
 * What lowers the confidence of a fighter's data on a frame.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "QualityCause".
 */
export type QualityCause = "no_footage" | "camera" | "overlap" | "image";

/**
 * MMA Fight Analyzer data contracts, schema version 1.12.0.
 */
export interface FightAnalyzerContracts {
  AnalysisExport?: AnalysisExport;
  AutoExclusionEdits?: AutoExclusionEdits;
  BoutConfig?: BoutConfig;
  BroadcastTimeline?: BroadcastTimeline;
  ErrorResponse?: ErrorResponse;
  EventTimeline?: EventTimeline;
  ExportRequest?: ExportRequest;
  FighterNames?: FighterNames;
  FighterSelection?: FighterSelection;
  HealthResponse?: HealthResponse;
  Job?: Job;
  JobList?: JobList;
  MatchSetup?: MatchSetup;
  MomentumTimeline?: MomentumTimeline;
  MotionTimeline?: MotionTimeline;
  PoseCacheManifest?: PoseCacheManifest;
  PoseChunk?: PoseChunk;
  PosePreview?: PosePreview;
  PoseSequence?: PoseSequence;
  RoundEdits?: RoundEdits;
  ScorebugRegion?: ScorebugRegion;
  Scorecards?: Scorecards;
  SegmentExclusions?: SegmentExclusions;
  SelectionCandidates?: SelectionCandidates;
  TrackQualityReport?: TrackQualityReport;
  TrackingTimeline?: TrackingTimeline;
  UploadLimits?: UploadLimits;
}
/**
 * The JSON file of an export.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "AnalysisExport".
 */
export interface AnalysisExport {
  /**
   * Whole video, before exclusions.
   */
  counts: FighterEventCounts[];
  /**
   * Meaning of each column of the CSV file.
   */
  csv_columns: {
    [k: string]: string;
  };
  /**
   * Damage signals (estimates), as on screen.
   */
  damage: DamageSignal[];
  data_origin: DataOrigin;
  events: FightEvent[];
  /**
   * Listed but not counted or scored.
   */
  excluded_event_ids: string[];
  exclusions: ExcludedSegment[];
  exported_at: string;
  fighters: Fighter[];
  /**
   * The analysis this was exported from.
   */
  job_id: string;
  momentum_contributions: MomentumContribution[];
  momentum_parameters: MomentumParameters;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  /**
   * AI round scoring (estimate, not official).
   */
  scorecards: Scorecards | null;
  selection: FighterSelection | null;
  /**
   * Pose, tracking, motion and momentum settings used.
   */
  settings: {
    [k: string]: unknown;
  };
  source_keys: SourceKeys;
  video: VideoInfo;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterEventCounts".
 */
export interface FighterEventCounts {
  /**
   * Control time (ground or clinch) during which he kept striking or threatening a submission.
   */
  active_control_s: number;
  advance_s: number;
  /**
   * Landed takedowns the opponent got up from at once.
   */
  brief_takedowns: number;
  /**
   * Estimated clinch control: time in the clinch after this fighter drove the opponent back (low confidence; the cage is not measured).
   */
  clinch_control_s: number;
  /**
   * Estimated time on top on the ground.
   */
  control_s: number;
  fighter_id: FighterId;
  get_ups: number;
  kick_attempts: number;
  /**
   * Strikes estimated as landed (events version 4 on).
   */
  landed_strikes: number;
  /**
   * Time with valid measurements of this fighter.
   */
  measured_s: number;
  possible_contacts: number;
  /**
   * Knockdowns scored by this fighter.
   */
  possible_knockdowns: number;
  /**
   * Takedowns landed by this fighter (brief ones included).
   */
  possible_takedowns: number;
  retreat_s: number;
  reversals: number;
  /**
   * Significant strike attempts.
   */
  significant_attempts: number;
  significant_landed: number;
  /**
   * Punch, knee, elbow and ground strike attempts.
   */
  strike_attempts: number;
  /**
   * Possible submission attempts (low confidence).
   */
  submission_attempts: number;
  /**
   * Takedown attempts, landed ones included (events version 5 on).
   */
  takedown_attempts: number;
}
/**
 * A sign that a fighter was damaged. An estimate with its confidence, never a fact.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "DamageSignal".
 */
export interface DamageSignal {
  attribution_confidence: number | null;
  attribution_uncertain: boolean;
  by_fighter: FighterId;
  confidence: number;
  data_origin: DataOrigin;
  /**
   * Signals that last (retreat, output drop).
   */
  end_ms: number | null;
  evidence: EvidenceSignal[];
  frame: number;
  kind: DamageKind;
  /**
   * The strike or knockdown it comes from.
   */
  linked_event_id: string | null;
  measures: {
    [k: string]: number;
  };
  note: string | null;
  severity: number;
  signal_id: string;
  target_fighter: FighterId;
  time_ms: number;
  type: DamageType;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FightEvent".
 */
export interface FightEvent {
  /**
   * Fighter performing the action.
   */
  actor: FighterId | null;
  /**
   * How sure the identity of the fighter(s) is over the event's frames (the actor; both for an event without one). None: analysed before identities carried it.
   */
  attribution_confidence: number | null;
  /**
   * Below the attribution threshold: 'Kime ait belirsiz'. Not part of the momentum.
   */
  attribution_uncertain: boolean;
  /**
   * Takedowns: the attacker stayed on top for less than the hold time because the opponent got up or came out on top at once. None: not a takedown, or it could not be told (measurement ended first).
   */
  brief: boolean | null;
  /**
   * Detector confidence, not ground truth.
   */
  confidence: number;
  data_origin: DataOrigin;
  end_frame: number;
  end_ms: number;
  event_id: string;
  /**
   * Signals behind the estimate.
   */
  evidence: EvidenceSignal[];
  limb: Limb | null;
  /**
   * Striking joint at the peak.
   */
  location: ImagePoint | null;
  /**
   * Measured values behind the detection (body units, seconds, cosines).
   */
  measures: {
    [k: string]: number;
  };
  note: string | null;
  /**
   * Strikes: estimated result. None: not a strike, or analysed before schema 1.11.0.
   */
  outcome: StrikeOutcome | null;
  /**
   * How sure the outcome is (None for unknown).
   */
  outcome_confidence: number | null;
  /**
   * Fastest moment of a strike / the fall.
   */
  peak_frame: number | null;
  peak_ms: number | null;
  /**
   * Strikes: where the fight was at the peak.
   */
  phase: FightPhase | null;
  /**
   * The striking limb overlapped the opponent in 2D; contact is not certain.
   */
  possible_contact: boolean;
  /**
   * Strikes: a significant strike (every strike at distance, power strikes in the clinch and on the ground). Says nothing about landing.
   */
  significant: boolean | null;
  start_frame: number;
  start_ms: number;
  /**
   * Fighter receiving the action.
   */
  target: FighterId | null;
  /**
   * Strikes: the opponent's zone the limb came closest to. None: not measurable.
   */
  target_zone: TargetZone | null;
  type: EventType;
}
/**
 * A point in analysis-video pixels.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ImagePoint".
 */
export interface ImagePoint {
  x: number;
  y: number;
}
/**
 * Part of the video that is not live fight time: marked by the user, or found
 * automatically (replays, stoppages, everything outside the rounds).
 *
 * An excluded part is not fight time: events whose moment (peak frame, else start
 * frame) lies in it are listed but neither counted nor scored, time-based points
 * (advancing, control) and measured time do not accrue in it, and the momentum
 * holds its value through it (decay runs on fight time).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExcludedSegment".
 */
export interface ExcludedSegment {
  /**
   * Automatic parts: id used to turn it off.
   */
  auto_id: string | null;
  /**
   * Automatic parts only.
   */
  confidence: number | null;
  /**
   * Last excluded frame (inclusive).
   */
  end_frame: number;
  note: string | null;
  reason: ExclusionReason;
  /**
   * Automatic parts: the evidence.
   */
  signals: ExclusionSignal[];
  source: ExclusionSource;
  start_frame: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Fighter".
 */
export interface Fighter {
  /**
   * Skeleton/overlay colour.
   */
  color: string;
  display_name: string;
  fighter_id: FighterId;
}
/**
 * One entry of the momentum ledger: where points came from.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MomentumContribution".
 */
export interface MomentumContribution {
  contribution_id: string;
  /**
   * Equals start_ms for one-off points.
   */
  end_ms: number;
  /**
   * Event the points come from, if any.
   */
  event_id: string | null;
  fighter_id: FighterId;
  /**
   * Points before decay (weight x quantity).
   */
  points: number;
  /**
   * 1 per attempt/event, seconds for time-based sources.
   */
  quantity: number;
  source: MomentumSource;
  start_ms: number;
}
/**
 * Starting design parameters of the experimental model (not validated weights).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MomentumParameters".
 */
export interface MomentumParameters {
  advance_per_s: number;
  contact_bonus: number;
  control_per_s: number;
  half_life_s: number;
  kick_attempt: number;
  knockdown: number;
  min_major_confidence: number;
  /**
   * Added to both sides; 4 gives 50/50 without data.
   */
  prior: number;
  strike_attempt: number;
  takedown: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Scorecards".
 */
export interface Scorecards {
  /**
   * Always true: not an official result.
   */
  ai_estimate: boolean;
  data_origin: DataOrigin;
  disclaimer: string;
  fighters: Fighter[];
  job_id: string;
  /**
   * @minItems 3
   * @maxItems 3
   */
  judges: JudgeScorecard[];
  method: string;
  round_summaries: RoundSummary[];
  rounds: RoundAssessment[];
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  setup: MatchSetup;
  verdict: MatchVerdict;
  warnings: string[];
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JudgeScorecard".
 */
export interface JudgeScorecard {
  judge: JudgeProfile;
  rounds: JudgeRoundScore[];
  total_blue: number;
  total_red: number;
  /**
   * None: the card is a draw.
   */
  winner: FighterId | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JudgeProfile".
 */
export interface JudgeProfile {
  description: string;
  judge_id: string;
  name: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JudgeRoundScore".
 */
export interface JudgeRoundScore {
  blue: number;
  criteria: CriterionMargin[];
  deciding_criterion: Criterion | null;
  /**
   * fighter_id -> points taken this round.
   */
  deductions: {
    [k: string]: number;
  };
  reasons: string[];
  red: number;
  round: number;
  /**
   * False: not enough data; the round is left out of the totals.
   */
  scored: boolean;
  /**
   * None: 10-10.
   */
  winner: FighterId | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "CriterionMargin".
 */
export interface CriterionMargin {
  blue: number;
  criterion: Criterion;
  /**
   * The difference was large enough for this judge.
   */
  decisive: boolean;
  red: number;
}
/**
 * Round across the three judges.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundSummary".
 */
export interface RoundSummary {
  blue: number;
  confidence: number;
  confidence_level: ConfidenceLevel;
  /**
   * Judges that gave this winner (or 10-10).
   */
  judges_agree: number;
  number: number;
  reason: string;
  /**
   * Most common red score among the judges.
   */
  red: number;
  scored: boolean;
  winner: FighterId | null;
}
/**
 * Evidence and confidence of one round; the same for all judges.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundAssessment".
 */
export interface RoundAssessment {
  confidence: number;
  confidence_level: ConfidenceLevel;
  confidence_notes: string[];
  damage: EdgeSummary;
  end_frame: number;
  end_s: number;
  /**
   * @minItems 2
   * @maxItems 2
   */
  evidence: FighterRoundEvidence[];
  grappling: EdgeSummary;
  key_moments: KeyMoment[];
  /**
   * False: no rounds were marked and the whole video stands in for round 1.
   */
  marked: boolean;
  not_measured: string[];
  number: number;
  /**
   * Shorter than the scheduled round length.
   */
  partial: boolean;
  /**
   * Fight time in the recording (excluded parts removed).
   */
  recorded_s: number;
  /**
   * Enough measured fight time to score the round.
   */
  scorable: boolean;
  start_frame: number;
  start_s: number;
  unscorable_reason: string | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "EdgeSummary".
 */
export interface EdgeSummary {
  /**
   * Who had the advantage, if the evidence shows one.
   */
  edge: FighterId | null;
  text: string;
}
/**
 * What the analysis measured for one fighter in one round (excluded parts left out).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterRoundEvidence".
 */
export interface FighterRoundEvidence {
  advance_s: number;
  /**
   * Estimated top control on the ground.
   */
  control_s: number;
  fighter_id: FighterId;
  identity_uncertain_s: number;
  kick_attempts: number;
  /**
   * Time this fighter could be measured.
   */
  measured_s: number;
  /**
   * Attempts whose limb overlapped the opponent in 2D.
   */
  possible_contact_strikes: number;
  /**
   * Possible contact followed by the opponent's head snapping (sign of impact, unverified).
   */
  possible_impact_strikes: number;
  /**
   * Scored by this fighter, with enough evidence.
   */
  possible_knockdowns: number;
  possible_takedowns: number;
  retreat_s: number;
  /**
   * Punch and knee attempts.
   */
  strike_attempts: number;
  /**
   * Takedowns followed by top position.
   */
  takedowns_to_control: number;
  /**
   * Possible knockdowns/takedowns below the evidence threshold.
   */
  uncertain_events: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "KeyMoment".
 */
export interface KeyMoment {
  confidence: number;
  event_id: string;
  fighter_id: FighterId | null;
  label: string;
  time_s: number;
  type: EventType;
  uncertain: boolean;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MatchSetup".
 */
export interface MatchSetup {
  /**
   * Automatic rounds the user removed (by number).
   *
   * @maxItems 5
   */
  cleared_rounds: number[];
  /**
   * @maxItems 20
   */
  deductions: PointDeduction[];
  ending: MatchEnding;
  /**
   * Mirrors BoutConfig.
   */
  round_length_s: number;
  /**
   * The user's round marks; each replaces the automatic round of the same number. Effective rounds: Job.rounds.
   *
   * @maxItems 5
   */
  rounds: RoundMark[];
  /**
   * Mirrors BoutConfig (Job.bout), which is the source since 1.7.0.
   */
  scheduled_rounds: number;
}
/**
 * A point taken by the referee (fouls cannot be detected from video: user input).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PointDeduction".
 */
export interface PointDeduction {
  fighter_id: FighterId;
  note: string | null;
  points: number;
  round: number;
}
/**
 * How the bout ended, as entered by the user (official information).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MatchEnding".
 */
export interface MatchEnding {
  method: FinishMethod;
  round: number | null;
  /**
   * Time into the final round.
   */
  time_s: number | null;
  /**
   * Required for finishes and disqualifications.
   */
  winner: FighterId | null;
}
/**
 * A round in the analysis video, marked by the user.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundMark".
 */
export interface RoundMark {
  /**
   * Last frame of the round (inclusive).
   */
  end_frame: number;
  number: number;
  start_frame: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MatchVerdict".
 */
export interface MatchVerdict {
  /**
   * Card totals, e.g. '29-28'.
   */
  cards: string[];
  confidence: number | null;
  confidence_level: ConfidenceLevel | null;
  decision_type: DecisionType | null;
  method: FinishMethod;
  notes: string[];
  reasons: string[];
  /**
   * 'ai_estimate' or 'user_input'.
   */
  source: string;
  status: VerdictStatus;
  summary: string;
  winner: FighterId | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterSelection".
 */
export interface FighterSelection {
  /**
   * @minItems 1
   * @maxItems 50
   */
  anchors: FighterAnchor[];
}
/**
 * A user selection: on `frame_index`, detection ids (as in that frame's
 * FrameRecord) of the red and blue corner fighters. `None` means the user
 * marked that fighter as not in the picture on this frame (close-ups).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterAnchor".
 */
export interface FighterAnchor {
  blue_detection_id: number | null;
  frame_index: number;
  red_detection_id: number | null;
}
/**
 * Cache entries the export was made from (the same ones the browser reads).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "SourceKeys".
 */
export interface SourceKeys {
  events: string;
  pose: string;
  scoring: string;
  tracking: string;
}
/**
 * Properties of the prepared (analysis) video that all frame indices and
 * pixel coordinates refer to. Width/height are the displayed size, i.e.
 * after applying the container rotation.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "VideoInfo".
 */
export interface VideoInfo {
  /**
   * Video codec name, e.g. 'h264'.
   */
  codec: string | null;
  /**
   * Duration in milliseconds.
   */
  duration_ms: number;
  /**
   * Frames per second (exact = fps_num / fps_den).
   */
  fps: number;
  /**
   * Constant frame rate denominator.
   */
  fps_den: number | null;
  /**
   * Constant frame rate numerator.
   */
  fps_num: number | null;
  /**
   * Number of decodable frames.
   */
  frame_count: number;
  has_audio: boolean;
  /**
   * Frame height in pixels.
   */
  height: number;
  /**
   * Rotation that was applied to reach width/height.
   */
  rotation_deg: 0 | 90 | 180 | 270;
  /**
   * Frame width in pixels.
   */
  width: number;
}
/**
 * Request body of PUT /jobs/{id}/exclusions/auto: the automatic parts the user turned
 * off, by auto_id (the complete list; the others apply).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "AutoExclusionEdits".
 */
export interface AutoExclusionEdits {
  /**
   * @maxItems 200
   */
  dismissed: string[];
}
/**
 * Bout format confirmed by the user ("Maç ayarları").
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "BoutConfig".
 */
export interface BoutConfig {
  /**
   * Corner names. Always filled in Job.bout; in a request null keeps them.
   */
  names: FighterNames | null;
  /**
   * Break between rounds.
   */
  rest_s: number;
  round_length_s: number;
  ruleset: Ruleset;
  /**
   * 3 for most bouts, 5 for title fights.
   */
  scheduled_rounds: number;
  title_fight: boolean;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterNames".
 */
export interface FighterNames {
  blue: string;
  red: string;
}
/**
 * The fight clock read from the scorebug, one sample per second of video
 * (null: no usable read and no safe interpolation).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "BroadcastTimeline".
 */
export interface BroadcastTimeline {
  confidence: number[];
  fps: number;
  job_id: string;
  remaining_s: (number | null)[];
  roi: ScorebugRoi | null;
  round: (number | null)[];
  /**
   * Automatic rounds (before the user's edits).
   */
  rounds: RoundSegment[];
  sample_hz: number;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  t_s: number[];
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ScorebugRoi".
 */
export interface ScorebugRoi {
  clock: ScreenRect;
  /**
   * Automatic: share of reads there that parsed as a clock in the frames searched; manual: share of seconds of video it read as a clock.
   */
  confidence: number;
  source: RoiSource;
}
/**
 * Rectangle in the analysis video as shares of its width and height (0..1).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ScreenRect".
 */
export interface ScreenRect {
  h: number;
  w: number;
  x: number;
  y: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundSegment".
 */
export interface RoundSegment {
  /**
   * Seconds left at the end: 0 = ran out; more = stopped early or cut off.
   */
  clock_end: number | null;
  /**
   * Fight clock (seconds left) when the round starts in the video.
   */
  clock_start: number | null;
  confidence: number;
  /**
   * Last frame of the round (inclusive).
   */
  end_frame: number;
  /**
   * Round number.
   */
  index: number;
  /**
   * Not the full round length in the recording (finish, or cut off).
   */
  partial: boolean;
  source: RoundSource;
  start_frame: number;
  /**
   * End of the last frame: (end_frame + 1) / fps.
   */
  video_end_s: number;
  video_start_s: number;
}
/**
 * Body of every 4xx/5xx response produced by the API itself.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ErrorResponse".
 */
export interface ErrorResponse {
  code: string;
  message: string;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "EventTimeline".
 */
export interface EventTimeline {
  /**
   * Damage signals (schema 1.11.0 on).
   */
  damage: DamageSignal[];
  data_origin: DataOrigin;
  events: FightEvent[];
  /**
   * @maxItems 2
   */
  fighters: Fighter[];
  job_id: string;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  video: VideoInfo;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExportRequest".
 */
export interface ExportRequest {
  options: ExportOptions;
}
/**
 * What is drawn on the exported video (CSV and JSON always contain everything).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExportOptions".
 */
export interface ExportOptions {
  /**
   * Attempt counters under the names.
   */
  counters: boolean;
  distance: boolean;
  /**
   * Strike flashes, possible-contact rings, major-event warnings.
   */
  effects: boolean;
  /**
   * Momentum bar with names and shares at the top.
   */
  momentum: boolean;
  /**
   * Other people (referee, spectators) in grey.
   */
  others: boolean;
  skeleton: boolean;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "HealthResponse".
 */
export interface HealthResponse {
  api_version: "v1";
  app_version: string;
  database: ComponentCheck;
  ffmpeg: FfmpegInfo;
  jobs: JobCounts;
  pose_model: PoseModelInfo;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  server_time: string;
  status: CheckStatus;
  worker: WorkerInfo;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ComponentCheck".
 */
export interface ComponentCheck {
  detail: string | null;
  status: CheckStatus;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FfmpegInfo".
 */
export interface FfmpegInfo {
  path: string | null;
  source: ("env" | "path" | "imageio-ffmpeg") | null;
  status: CheckStatus;
  version: string | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JobCounts".
 */
export interface JobCounts {
  awaiting_selection: number;
  cancelled: number;
  completed: number;
  failed: number;
  queued: number;
  running: number;
  total: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseModelInfo".
 */
export interface PoseModelInfo {
  name: string;
  /**
   * Whether the weights file exists locally.
   */
  present: boolean;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "WorkerInfo".
 */
export interface WorkerInfo {
  compute: ComputeInfo | null;
  last_heartbeat: string | null;
  pid: number | null;
  status: CheckStatus;
  worker_id: string | null;
}
/**
 * Inference device chosen by the worker (detected with PyTorch).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ComputeInfo".
 */
export interface ComputeInfo {
  cpu_threads: number;
  cuda_available: boolean;
  cuda_version: string | null;
  device: "cpu" | "cuda";
  device_name: string;
  note: string | null;
  requested: "auto" | "cpu" | "cuda";
  torch_version: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Job".
 */
export interface Job {
  /**
   * How many times a worker started this job.
   */
  attempts: number;
  /**
   * Automatic excluded parts: time outside the rounds in effect, detected replays and stoppages. Those not dismissed apply together with `exclusions`; the list in use is outputs.scoring.exclusions.
   */
  auto_exclusions: AutoExclusion[];
  bout: BoutConfig;
  cancel_requested: boolean;
  created_at: string;
  error: JobError | null;
  /**
   * Parts excluded from the analysis by the user (e.g. replays).
   */
  exclusions: ExcludedSegment[];
  /**
   * Names and colours, red first.
   */
  fighters: Fighter[];
  finished_at: string | null;
  job_id: string;
  job_type: JobType;
  /**
   * Rounds, ending and deductions entered by the user.
   */
  match: MatchSetup | null;
  message: string | null;
  /**
   * Parts made by an older version of the analysis ('yeniden işle').
   */
  outdated: OutdatedReason[];
  outputs: JobOutputs;
  /**
   * Overall progress, 0..1.
   */
  progress: number;
  progress_detail: StageProgress | null;
  /**
   * Automatic rounds left out, and why.
   */
  round_notes: RoundNote[];
  /**
   * Effective rounds: the user's marks over the automatic ones.
   */
  rounds: RoundSegment[];
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  selection: FighterSelection | null;
  source: SourceVideo | null;
  /**
   * Stage currently/last running.
   */
  stage: PipelineStage | null;
  started_at: string | null;
  status: JobStatus;
  updated_at: string;
  /**
   * Analysis video properties.
   */
  video: VideoInfo | null;
}
/**
 * An automatic excluded part and whether the user turned it off ("Geri al").
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "AutoExclusion".
 */
export interface AutoExclusion {
  /**
   * Automatic parts: id used to turn it off.
   */
  auto_id: string | null;
  /**
   * Automatic parts only.
   */
  confidence: number | null;
  /**
   * Turned off by the user: not applied.
   */
  dismissed: boolean;
  /**
   * Last excluded frame (inclusive).
   */
  end_frame: number;
  note: string | null;
  reason: ExclusionReason;
  /**
   * Automatic parts: the evidence.
   */
  signals: ExclusionSignal[];
  source: ExclusionSource;
  start_frame: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JobError".
 */
export interface JobError {
  /**
   * Machine-readable error code, e.g. 'stage_not_implemented'.
   */
  code: string;
  message: string;
  stage: PipelineStage | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JobOutputs".
 */
export interface JobOutputs {
  analysis_video: AnalysisVideo | null;
  broadcast: BroadcastSummary | null;
  events: EventsSummary | null;
  export: ExportSummary | null;
  pose: PoseSummary | null;
  scoring: ScoringSummary | null;
  tracking: TrackingSummary | null;
  tracking_prep: TrackingPrepSummary | null;
}
/**
 * Constant-frame-rate, browser-playable H.264 copy used by both the
 * analysis engine and the browser.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "AnalysisVideo".
 */
export interface AnalysisVideo {
  cache_hit: boolean;
  cache_key: string;
  sha256: string;
  size_bytes: number;
  transcode: TranscodeInfo;
  video: VideoInfo;
}
/**
 * Settings used to produce the analysis copy (part of its cache key).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TranscodeInfo".
 */
export interface TranscodeInfo {
  audio_bitrate_k: number;
  crf: number;
  ffmpeg_version: string | null;
  max_fps: number;
  max_short_side: number;
  preset: string;
  /**
   * Bumped whenever the FFmpeg recipe changes.
   */
  version: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "BroadcastSummary".
 */
export interface BroadcastSummary {
  cache_hit: boolean;
  cache_key: string;
  /**
   * Share of seconds with a usable clock read.
   */
  clock_share: number;
  method: string;
  names: NameSuggestion | null;
  notes: BroadcastNote[];
  ocr_available: boolean;
  ocr_model: string | null;
  processing_s: number;
  roi: ScorebugRoi | null;
  /**
   * Automatic rounds; Job.rounds applies the user's edits.
   */
  rounds: RoundSegment[];
  /**
   * A frame that shows the scorebug (for drawing the clock rectangle).
   */
  scorebug_frame: number | null;
  /**
   * Parts found from the broadcast signals: replays, stoppages, and the stretches before the first / after the last clock round without a scorebug. Job.auto_exclusions combines them with the rounds in effect.
   */
  segments: ExcludedSegment[];
  /**
   * Version of the broadcast analysis that made this (1: rounds only; 2: replays, stoppages, non-fight parts).
   */
  version: number;
}
/**
 * Names read from the scorebug. A suggestion only: never applied without the user.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "NameSuggestion".
 */
export interface NameSuggestion {
  blue: string | null;
  confidence: number;
  /**
   * As read left of the clock, e.g. 'VOLKANOVSKI'.
   */
  left: string | null;
  /**
   * Suggested red corner name (left by broadcast convention), title case.
   */
  red: string | null;
  right: string | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "BroadcastNote".
 */
export interface BroadcastNote {
  code: BroadcastNoteCode;
  round: number | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "EventsSummary".
 */
export interface EventsSummary {
  cache_hit: boolean;
  cache_key: string;
  /**
   * Frames whose camera motion is known.
   */
  camera_known_share: number;
  damage_signals: number;
  events: number;
  /**
   * @maxItems 2
   */
  fighters: FighterEventCounts[];
  method: string;
  /**
   * Grappling states (events version 5 on).
   */
  phases: PhaseTimes | null;
  /**
   * EVENTS_VERSION of the result (0: stored before it was kept).
   */
  version: number;
}
/**
 * Seconds of the video in each grappling state (whole video, before exclusions).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PhaseTimes".
 */
export interface PhaseTimes {
  clinch_s: number;
  distance_s: number;
  /**
   * On the ground with a clear top.
   */
  ground_s: number;
  scramble_s: number;
  /**
   * A fighter was not measured.
   */
  unknown_s: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExportSummary".
 */
export interface ExportSummary {
  events: number;
  files: ExportFile[];
  /**
   * Displayed share on the last frame.
   */
  final_red_share: number;
  frames: number;
  has_audio: boolean;
  options: ExportOptions;
  source_job_id: string;
  source_keys: SourceKeys;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ExportFile".
 */
export interface ExportFile {
  bytes: number;
  content_type: string;
  kind: ExportFileKind;
  name: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseSummary".
 */
export interface PoseSummary {
  cache_hit: boolean;
  cache_key: string;
  detection_count: number;
  frame_count: number;
  /**
   * Most people detected in a single frame.
   */
  max_persons: number;
  model: ModelInfo;
  /**
   * Inference wall time.
   */
  processing_s: number | null;
  settings: PoseAnalysisSettings;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ModelInfo".
 */
export interface ModelInfo {
  /**
   * 'cpu' or 'cuda:0'.
   */
  device: string | null;
  /**
   * e.g. ultralytics version.
   */
  framework_version: string | null;
  /**
   * Model file name, e.g. 'yolo26s-pose.pt'.
   */
  name: string;
  /**
   * Official download location.
   */
  source_url: string | null;
  weights_sha256: string | null;
}
/**
 * Inference settings; part of the pose cache key.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseAnalysisSettings".
 */
export interface PoseAnalysisSettings {
  /**
   * Minimum person detection confidence.
   */
  conf: number;
  /**
   * 1 = every frame is analysed.
   */
  frame_step: number;
  /**
   * Model input size in pixels.
   */
  imgsz: number;
  /**
   * NMS IoU threshold (ignored by NMS-free models).
   */
  iou: number;
  /**
   * Maximum people per frame.
   */
  max_det: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ScoringSummary".
 */
export interface ScoringSummary {
  cache_hit: boolean;
  cache_key: string;
  contributions: number;
  /**
   * Excluded parts applied: the user's and the automatic ones in effect, merged.
   */
  exclusions: ExcludedSegment[];
  final_red_share: number;
  parameters: MomentumParameters;
  /**
   * Events left out because it is uncertain whose they are ('Kime ait belirsiz').
   */
  unattributed_events: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackingSummary".
 */
export interface TrackingSummary {
  anchor_conflicts: number;
  anchors: FighterAnchor[];
  /**
   * None: not enough confident stretches.
   */
  appearance: AppearanceSummary | null;
  cache_hit: boolean;
  cache_key: string;
  /**
   * Camera cuts the preparation missed, found by the identity layer (frames).
   */
  extra_cuts: number[];
  fighters: FighterTrackStats[];
  /**
   * Times a fighter's identity moved directly onto a track another person held.
   */
  identity_switches: number;
  method: string;
  review_points: ReviewPoint[];
  shots: ShotInfo[];
  /**
   * Tracker continuations rejected because appearance pointed to someone else.
   */
  swap_corrections: number;
  uncertain_segments: UncertainSegment[];
  /**
   * Version of the identity layer (0: before version 6).
   */
  version: number;
}
/**
 * The appearance model the identities were assigned with (v2 Bölüm 2c): samples of each
 * fighter's shorts and torso from confident stretches all over the video, and of the third
 * persons (referee, corner staff) seen next to both fighters.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "AppearanceSummary".
 */
export interface AppearanceSummary {
  blue_samples: number;
  blue_shots: number;
  /**
   * Red / blue box height while both stand apart (median). Reported only: it is not used to tell the fighters apart.
   */
  height_ratio: number | null;
  red_samples: number;
  /**
   * Camera shots the red corner's samples come from.
   */
  red_shots: number;
  /**
   * Samples of people who are neither fighter.
   */
  third_samples: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterTrackStats".
 */
export interface FighterTrackStats {
  fighter_id: FighterId;
  longest_uncertain_ms: number;
  mean_confidence: number;
  occluded_frames: number;
  /**
   * Identity re-found after loss or a camera cut.
   */
  reacquisitions: number;
  /**
   * Times the temporary tracker id under this fighter changed.
   */
  track_changes: number;
  tracked_frames: number;
  uncertain_frames: number;
  uncertain_ms: number;
}
/**
 * Moment worth checking by eye (identity re-found with a small margin,
 * a tracker swap that was overridden, ...).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ReviewPoint".
 */
export interface ReviewPoint {
  fighter_id: FighterId;
  frame_index: number;
  /**
   * reacquired_low_margin | swap_corrected | after_cut
   */
  kind: string;
  margin: number | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ShotInfo".
 */
export interface ShotInfo {
  end_frame: number;
  index: number;
  start_frame: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "UncertainSegment".
 */
export interface UncertainSegment {
  end_frame: number;
  fighter_id: FighterId;
  reason: UncertainReason;
  start_frame: number;
}
/**
 * Selection-independent preparation (cuts, tracklets, appearance).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackingPrepSummary".
 */
export interface TrackingPrepSummary {
  cache_hit: boolean;
  cache_key: string;
  candidates: number;
  /**
   * Frames where a new camera shot starts.
   */
  cuts: number[];
  shots: number;
  /**
   * Short-term tracker used inside shots.
   */
  tracker: string;
  tracklets: number;
}
/**
 * Measured progress of the current stage.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "StageProgress".
 */
export interface StageProgress {
  /**
   * Units processed so far (e.g. frames).
   */
  done: number;
  /**
   * Estimated seconds left; null until enough measurements.
   */
  eta_s: number | null;
  note: string | null;
  /**
   * Latest preview number.
   */
  preview_seq: number | null;
  /**
   * Measured units per second.
   */
  rate_per_s: number | null;
  stage: PipelineStage;
  total: number | null;
  unit: ProgressUnit;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundNote".
 */
export interface RoundNote {
  code: RoundNoteCode;
  /**
   * The other round involved, if any.
   */
  other: number | null;
  round: number;
}
/**
 * The file the user uploaded, as probed by FFmpeg.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "SourceVideo".
 */
export interface SourceVideo {
  codec: string | null;
  container: string | null;
  duration_ms: number;
  filename: string;
  /**
   * Average frame rate reported by FFmpeg.
   */
  fps: number | null;
  has_audio: boolean;
  /**
   * Displayed height (rotation applied).
   */
  height: number;
  rotation_deg: 0 | 90 | 180 | 270;
  sha256: string;
  size_bytes: number;
  /**
   * Displayed width (rotation applied).
   */
  width: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "JobList".
 */
export interface JobList {
  jobs: Job[];
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  /**
   * Number of jobs in the store (may exceed len(jobs)).
   */
  total: number;
}
/**
 * Red share(t) = 100 x (m_red + prior) / (m_red + m_blue + 2 x prior); blue = 100 - red.
 * m(t) = sum of ledger points, each halved every half_life_s seconds after it was earned.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MomentumTimeline".
 */
export interface MomentumTimeline {
  contributions: MomentumContribution[];
  data_origin: DataOrigin;
  /**
   * Excluded parts the ledger was computed with (already applied).
   */
  exclusions: ExcludedSegment[];
  /**
   * Experimental index, not a win probability.
   */
  experimental: boolean;
  /**
   * A fighter could not be measured at the sample.
   */
  insufficient: boolean[];
  job_id: string;
  m_blue: number[];
  m_red: number[];
  parameters: MomentumParameters;
  /**
   * 0..100; the blue share is 100 minus this.
   */
  red_share: number[];
  sample_hz: number;
  sample_ms: number[];
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  /**
   * Events left out of the ledger because it is uncertain whose they are (outside excluded parts).
   */
  unattributed_event_ids: string[];
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "MotionTimeline".
 */
export interface MotionTimeline {
  /**
   * Camera motion could be estimated from the background.
   */
  camera_known: boolean[];
  data_origin: DataOrigin;
  /**
   * Distance between the fighters' hip centres, body units.
   */
  distance: (number | null)[];
  /**
   * @maxItems 2
   */
  fighters: FighterSignals[];
  job_id: string;
  /**
   * Grappling state at the sample (most of its frames; null: not measured). Empty: analysed before events version 5.
   */
  phase: (GrapplingState | null)[];
  sample_hz: number;
  sample_ms: number[];
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterSignals".
 */
export interface FighterSignals {
  /**
   * Hand and foot motion relative to the body, 0..1.
   */
  activity: (number | null)[];
  /**
   * Hip centre toward (+) / away from (-) the opponent, camera motion removed, body units/s.
   */
  approach_speed: (number | null)[];
  /**
   * Back to the camera on most frames of the sample (nose and eyes not measured while both shoulders are). How well his strikes can be seen depends on it. Empty: analysed before events version 5.
   */
  facing_away: (boolean | null)[];
  fighter_id: FighterId;
  /**
   * Ankles relative to the hips, body units/s.
   */
  foot_speed: (number | null)[];
  /**
   * Wrists relative to the hips, body units/s.
   */
  hand_speed: (number | null)[];
  movement: (Movement | null)[];
  posture: (Posture | null)[];
  /**
   * Fighter verified with usable joints at the sample.
   */
  valid: boolean[];
  /**
   * Share of the sample's frames on which his wrists are measured, 0..1.
   */
  wrists_measured: (number | null)[];
}
/**
 * manifest.json of a pose cache entry. Per-frame data lives next to it in
 * NumPy .npy files (loaded with allow_pickle=False):
 * frame_index[F] int32, timestamp_ms[F] float64, det_offsets[F+1] int64
 * (detections of frame i are rows det_offsets[i]:det_offsets[i+1]),
 * boxes[N,4] float32 (x1,y1,x2,y2), box_conf[N] float32,
 * keypoints[N,17,3] float32 (x, y, confidence in KeypointName order).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseCacheManifest".
 */
export interface PoseCacheManifest {
  arrays: {
    [k: string]: PoseArrayInfo;
  };
  cache_key: string;
  created_at: string;
  detection_count: number;
  frame_count: number;
  key_inputs: {
    [k: string]: unknown;
  };
  keypoint_names: KeypointName[];
  max_persons: number;
  model: ModelInfo;
  processing_s: number | null;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  settings: PoseAnalysisSettings;
  video: VideoInfo;
  video_sha256: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseArrayInfo".
 */
export interface PoseArrayInfo {
  dtype: string;
  file: string;
  sha256: string;
  shape: number[];
}
/**
 * A window of consecutive frames served to the UI.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseChunk".
 */
export interface PoseChunk {
  data_origin: DataOrigin;
  frames: FrameRecord[];
  job_id: string;
  keypoint_names: KeypointName[];
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  start_frame: number;
  video: VideoInfo;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FrameRecord".
 */
export interface FrameRecord {
  detections: PersonDetection[];
  /**
   * Identity state per fighter once tracking has run.
   */
  fighters: FighterFrameState[];
  /**
   * 0-based index into the analysis video.
   */
  frame_index: number;
  /**
   * Presentation time: frame_index / fps.
   */
  timestamp_ms: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PersonDetection".
 */
export interface PersonDetection {
  bbox: BoundingBox;
  /**
   * Person detection confidence.
   */
  confidence: number;
  /**
   * Index of this detection within its frame.
   */
  detection_id: number;
  /**
   * Resolved fighter identity, null for referee/others/unknown.
   */
  fighter_id: FighterId | null;
  /**
   * Joints in KeypointName order.
   *
   * @minItems 17
   * @maxItems 17
   */
  keypoints: Keypoint[];
  /**
   * Raw tracker id; may change after occlusions.
   */
  track_id: number | null;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "BoundingBox".
 */
export interface BoundingBox {
  x1: number;
  x2: number;
  y1: number;
  y2: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "Keypoint".
 */
export interface Keypoint {
  /**
   * Model confidence for this joint.
   */
  confidence: number;
  /**
   * Horizontal pixel coordinate.
   */
  x: number;
  /**
   * Vertical pixel coordinate.
   */
  y: number;
}
/**
 * Identity state of one fighter in one frame.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterFrameState".
 */
export interface FighterFrameState {
  confidence: number;
  /**
   * Detection in this frame, if any.
   */
  detection_id: number | null;
  fighter_id: FighterId;
  state: TrackState;
}
/**
 * Latest processed frame while pose extraction runs (sent at low rate).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PosePreview".
 */
export interface PosePreview {
  frame: FrameRecord;
  height: number;
  job_id: string;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  /**
   * Increments with every new preview.
   */
  seq: number;
  /**
   * Analysis frame width the coordinates refer to.
   */
  width: number;
}
/**
 * Pose output of one job (export format).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "PoseSequence".
 */
export interface PoseSequence {
  data_origin: DataOrigin;
  frames: FrameRecord[];
  job_id: string;
  keypoint_names: KeypointName[];
  model: ModelInfo;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  skeleton: SkeletonFormat;
  video: VideoInfo;
}
/**
 * Request body of PUT /jobs/{id}/rounds. A mark replaces the automatic round of
 * the same number; cleared numbers are automatic rounds the user removed.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "RoundEdits".
 */
export interface RoundEdits {
  /**
   * @maxItems 5
   */
  cleared_rounds: number[];
  /**
   * @maxItems 5
   */
  rounds: RoundMark[];
}
/**
 * Request body of PUT /jobs/{id}/scorebug: the user's clock rectangle; null = automatic.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "ScorebugRegion".
 */
export interface ScorebugRegion {
  clock: ScreenRect | null;
}
/**
 * Request body: the complete list of the user's excluded parts (replaces the previous one).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "SegmentExclusions".
 */
export interface SegmentExclusions {
  /**
   * @maxItems 100
   */
  segments: ExcludedSegment[];
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "SelectionCandidates".
 */
export interface SelectionCandidates {
  frames: SelectionCandidate[];
  job_id: string;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  video: VideoInfo;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "SelectionCandidate".
 */
export interface SelectionCandidate {
  detections: PersonDetection[];
  frame_index: number;
  /**
   * How well both fighters are visible and separated.
   */
  score: number;
  shot_index: number;
  timestamp_ms: number;
}
/**
 * Data quality for the whole bout and for every round in effect.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackQualityReport".
 */
export interface TrackQualityReport {
  fps: number;
  job_id: string;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
  scopes: QualityScope[];
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "QualityScope".
 */
export interface QualityScope {
  end_frame: number;
  /**
   * @maxItems 2
   */
  fighters: TrackQuality[];
  /**
   * Round number; None: the whole bout.
   */
  round: number | null;
  start_frame: number;
}
/**
 * Data quality of one fighter in a frame range (excluded parts are not fight time).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackQuality".
 */
export interface TrackQuality {
  /**
   * Largest first; a frame can have several causes.
   */
  causes: CauseShare[];
  fighter_id: FighterId;
  /**
   * Frames of fight time in the range.
   */
  frames: number;
  /**
   * Times the temporary tracker id under the fighter changed.
   */
  identity_changes: number;
  longest_uncertain_ms: number;
  measurable_share: number;
  /**
   * Overlap frames carried by tracker continuity.
   */
  occluded_share: number;
  uncertain_ms: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "CauseShare".
 */
export interface CauseShare {
  cause: QualityCause;
  /**
   * Share of the fight time in the range with this cause.
   */
  share: number;
}
/**
 * Run-length encoded identity states for the whole video (for the UI timeline).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackingTimeline".
 */
export interface TrackingTimeline {
  cuts: number[];
  fighters: FighterTimeline[];
  fps: number;
  frame_count: number;
  job_id: string;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "FighterTimeline".
 */
export interface FighterTimeline {
  /**
   * Frames at which the temporary tracker id under the fighter changed.
   */
  changes: number[];
  fighter_id: FighterId;
  /**
   * None: analysed before the quality data existed (process again).
   */
  quality: QualityRun[] | null;
  runs: TrackStateRun[];
}
/**
 * A stretch of frames that is not measurable or has causes that lower the confidence.
 * Frames in no run are measurable without a known cause.
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "QualityRun".
 */
export interface QualityRun {
  causes: QualityCause[];
  end_frame: number;
  /**
   * Identity verified with a detection and enough of the body measured.
   */
  measurable: boolean;
  start_frame: number;
}
/**
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "TrackStateRun".
 */
export interface TrackStateRun {
  end_frame: number;
  start_frame: number;
  state: TrackState;
}
/**
 * Server-side upload limits (also checked by the UI before uploading).
 *
 * This interface was referenced by `FightAnalyzerContracts`'s JSON-Schema
 * via the `definition` "UploadLimits".
 */
export interface UploadLimits {
  extensions: string[];
  max_bytes: number;
  max_duration_s: number;
  max_long_side: number;
  max_short_side: number;
  min_duration_s: number;
  min_short_side: number;
  /**
   * Semantic version of the contract this document follows.
   */
  schema_version: string;
}

/** Contract version this UI was built against. */
export const SCHEMA_VERSION = "1.12.0";
