/**
 * View models for the result/selection screens.
 *
 * The backend contracts for statistics and momentum arrive with the scoring
 * stage; until then the UI works on these view types. A `null` value always
 * means "no measurement" and is rendered as "—", never as a guessed number.
 */
import type { DamageKind, DamageType, DataOrigin, EventType, StrikeOutcome, TargetZone } from "../contracts/generated";

/** Corner colours. Red = fighter_a, blue (drawn in cyan) = fighter_b. */
export type Side = "red" | "blue";
export const SIDES: readonly Side[] = ["red", "blue"];

export interface FighterView {
  side: Side;
  name: string;
}

export interface StatsView {
  strikeAttempts: number | null;
  kicks: number | null;
  /** 0..100 activity index. */
  activity: number | null;
  /** Share of time spent pressing forward, 0..100. */
  pressure: number | null;
  /** Share of movement time advancing / retreating, 0..100. */
  advance: number | null;
  retreat: number | null;
  /** Estimated control time in seconds. */
  controlS: number | null;
  /** Possible significant events (e.g. possible knockdown). */
  significant: number | null;
}

export const EMPTY_STATS: StatsView = {
  strikeAttempts: null,
  kicks: null,
  activity: null,
  pressure: null,
  advance: null,
  retreat: null,
  controlS: null,
  significant: null,
};

/** Uncertainty label of an event (shown next to it; never hidden by an effect). */
export interface EventTag {
  label: string;
  tone: "amber" | "muted";
  title: string;
}

export interface TimelineEvent {
  id: string;
  type: EventType;
  side: Side | null;
  /** Event moment (peak) in seconds; lists and the timeline use it. */
  startS: number;
  endS: number;
  confidence: number;
  /** Possible significant event, highlighted in amber. */
  significant: boolean;
  note: string | null;
  origin: DataOrigin;
  tags?: EventTag[];
  /** In a part the user excluded (e.g. a replay): listed, not counted or scored. */
  excluded?: boolean;
  /** Strikes (schema 1.11.0 on): estimated outcome, target zone and significant strike. */
  outcome?: StrikeOutcome | null;
  zone?: TargetZone | null;
  significantStrike?: boolean | null;
  /** Seen only by inferring the opponent's identity: listed, not counted, no momentum. */
  inferred?: boolean;
}

/** A damage signal in the event list (an estimate; v2 Bölüm 3a). */
export interface DamageView {
  id: string;
  type: DamageType;
  kind: DamageKind;
  /** Credited fighter (the one who caused it) and the damaged one. */
  side: Side;
  target: Side;
  startS: number;
  endS: number | null;
  severity: number;
  confidence: number;
  /** Whose it is was inferred from the other fighter (knockdowns). */
  inferred: boolean;
  /** Below the attribution threshold ("Kime ait belirsiz"). */
  uncertain: boolean;
  excluded: boolean;
  note: string | null;
}

/** Ids of people visible in a frame (tracker ids in real data). */
export type PersonId = string;

export interface Detection {
  personId: PersonId;
  /** Box in frame pixels. */
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
}

export type Assignment = Record<Side, PersonId | null>;
/** Pick value meaning "this fighter is not in the picture on this frame" (corrections on close-ups). */
export const NOT_IN_VIEW = "not-in-view";
