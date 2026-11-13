import { useId } from "react";
import type {
  BoutConfig,
  BroadcastSummary,
  NameSuggestion,
  RoundNote,
  RoundSegment,
} from "../../contracts/generated";
import { MATCH_LABELS as L, ROUND_EDIT_LABELS, UI_LABELS } from "../../labels";
import { formatClock } from "../../player/clock";
import { Badge, Button, Card, DemoTag, HelpTip, SectionHeading, SegmentedControl, cx } from "../../ui";

type RoundOption = "3" | "5";

export interface RoiControls {
  /** Drawing the rectangle on the frame above. */
  editing: boolean;
  source: "auto" | "manual" | null;
  canSave: boolean;
  busy: boolean;
  onStart: () => void;
  onSave: () => void;
  onCancel: () => void;
  onReset?: () => void;
}

export interface NameControls {
  suggestion: NameSuggestion;
  /** Corners the suggestion would fill; empty: both names are already entered. */
  canApply: boolean;
  onApply: () => void;
}

export interface RoundRowActions {
  onSeek?: (r: RoundSegment) => void;
  onRemove?: (r: RoundSegment) => void;
  /** Shown for manual rounds that replace or removed an automatic one. */
  canRevert?: (r: RoundSegment) => boolean;
  onRevert?: (r: RoundSegment) => void;
}

const span = (r: RoundSegment) => `${formatClock(r.video_start_s, true)}–${formatClock(r.video_end_s, true)}`;

/** One line per effective round: number, video span, where it comes from and how sure it is. */
export function RoundRows({ rounds, actions, compact = false }: {
  rounds: RoundSegment[];
  actions?: RoundRowActions;
  compact?: boolean;
}) {
  return (
    <ul className={cx("mset__rounds", compact && "mset__rounds--compact")}>
      {rounds.map((r) => (
        <li key={r.index} className={cx("mset__round", `mset__round--${r.source}`)}>
          <Badge tone="neutral" className="mset__rno num">{L.round(r.index)}</Badge>
          {actions?.onSeek ? (
            <button type="button" className="linkbtn num" onClick={() => actions.onSeek?.(r)}>{span(r)}</button>
          ) : <span className="num">{span(r)}</span>}
          <span className="mset__meta">
            {L.source[r.source]}
            {r.source !== "manual" && <> · <span className="num">{L.confidence(Math.round(r.confidence * 100))}</span></>}
            {r.clock_end != null && r.clock_end > 0 && <> · {L.clockEnd(formatClock(r.clock_end))}</>}
          </span>
          {r.partial && (
            <span className="mset__partial">
              <Badge tone="warning">{L.partial}</Badge>
              <HelpTip label={UI_LABELS.help(L.partial)} align="end">{L.partialHelp}</HelpTip>
            </span>
          )}
          {(actions?.onRemove || actions?.onRevert) && (
            <span className="mset__actions">
              {actions.onRevert && actions.canRevert?.(r) && (
                <Button size="sm" variant="ghost" onClick={() => actions.onRevert?.(r)}>{L.roi.reset}</Button>
              )}
              {actions.onRemove && (
                <button type="button" className="excl__remove" aria-label={`${L.round(r.index)} ×`}
                        title={`${L.round(r.index)} ×`} onClick={() => actions.onRemove?.(r)}>×</button>
              )}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * "Maç ayarları": round count, title fight, the round boundaries found in the
 * video and, on the selection screen, the clock area and the names read on the
 * scorebug. Changes are saved at once (nothing is recomputed); without
 * `onBout` the card is read-only (Demo).
 */
export function MatchSettings({ bout, rounds, broadcast, roundNotes, onBout, busy = false, problem = null, demo = false,
                                roi, names, actions, restore, headingLevel = 2 }: {
  bout: BoutConfig;
  rounds: RoundSegment[];
  /** null: the analysis has no broadcast step yet (older version). */
  broadcast: BroadcastSummary | null;
  roundNotes: RoundNote[];
  onBout?: (next: BoutConfig) => void;
  busy?: boolean;
  problem?: string | null;
  demo?: boolean;
  roi?: RoiControls;
  names?: NameControls;
  actions?: RoundRowActions;
  /** Automatic rounds the user removed, offered back. */
  restore?: { numbers: number[]; onRestore: (n: number) => void };
  headingLevel?: 2 | 3;
}) {
  const titleId = useId();
  const options = ([3, 5] as const).map((n) => ({ value: String(n) as RoundOption, label: L.roundsOption(n) }));
  const setRounds = (v: RoundOption) => onBout?.({ ...bout, scheduled_rounds: Number(v) });
  const toggleTitle = () => onBout?.({
    ...bout, title_fight: !bout.title_fight, scheduled_rounds: bout.title_fight ? bout.scheduled_rounds : 5,
  });
  const notes = [
    ...(broadcast?.notes ?? []).map((n) => L.notes[n.code](n.round ?? null)),
    ...roundNotes.map((n) => L.roundNotes[n.code](n.round, n.other ?? null)),
  ];
  return (
    <Card className="mset" aria-labelledby={titleId}>
      <SectionHeading id={titleId} level={headingLevel} title={<>{L.title}{demo && <> <DemoTag small /></>}</>}
                      description={L.description} />
      <div className="mset__format">
        <SegmentedControl label={L.roundsLabel} options={options} value={String(bout.scheduled_rounds) as RoundOption}
                          onChange={onBout && !busy ? setRounds : undefined} />
        <button type="button" role="switch" aria-checked={bout.title_fight} className="switch"
                disabled={!onBout || busy} onClick={toggleTitle}>
          <span className="switch__track" aria-hidden="true"><span className="switch__thumb" /></span>
          {L.titleFight}
        </button>
        <span className="mset__hint">{busy ? L.saving : L.titleFightHint}</span>
      </div>

      <div className="mset__found">
        <h4 className="mset__sub">{L.found}</h4>
        {broadcast === null && !demo ? <p className="mset__empty">{L.pending}</p>
          : rounds.length === 0 ? <p className="mset__empty">{L.none}</p>
            : <RoundRows rounds={rounds} actions={actions} />}
        {restore && restore.numbers.length > 0 && (
          <ul className="mset__restore">
            {restore.numbers.map((n) => (
              <li key={n}>
                {ROUND_EDIT_LABELS.removed(n)}{" "}
                <button type="button" className="linkbtn" onClick={() => restore.onRestore(n)}>{L.roi.reset}</button>
              </li>
            ))}
          </ul>
        )}
        {notes.length > 0 && (
          <ul className="mset__notes">{notes.map((n) => <li key={n}>{n}</li>)}</ul>
        )}
        <p className="mset__ai">{L.aiNote}</p>
      </div>

      {roi && (
        <div className="mset__roi">
          {roi.editing ? (
            <>
              <p className="mset__hint">{L.roi.hint}</p>
              <div className="mset__buttons">
                <Button variant="primary" size="sm" disabled={!roi.canSave || roi.busy} onClick={roi.onSave}>
                  {L.roi.save}
                </Button>
                <Button size="sm" onClick={roi.onCancel}>{L.roi.cancel}</Button>
              </div>
            </>
          ) : (
            <div className="mset__buttons">
              {roi.source && <span className="mset__hint">{roi.source === "manual" ? L.roi.manual : L.roi.auto}</span>}
              <Button size="sm" disabled={roi.busy} onClick={roi.onStart}>{L.roi.fix}</Button>
              {roi.source === "manual" && roi.onReset && (
                <Button size="sm" variant="ghost" disabled={roi.busy} onClick={roi.onReset}>{L.roi.reset}</Button>
              )}
            </div>
          )}
        </div>
      )}

      {names && (
        <div className="mset__names">
          <h4 className="mset__sub">{L.names.title}</h4>
          <p className="mset__read">{L.names.read(names.suggestion.left ?? null, names.suggestion.right ?? null)}</p>
          <div className="mset__buttons">
            <Button size="sm" disabled={!names.canApply} onClick={names.onApply}>{L.names.apply}</Button>
          </div>
          <p className="mset__hint">{names.canApply ? L.names.hint : L.names.nothing}</p>
        </div>
      )}
      {demo && <p className="mset__hint">{L.demo}</p>}
      {problem && <p className="inline-warn" role="alert">{problem}</p>}
    </Card>
  );
}
