import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { SELECTION_LABELS as L, SIDE_LABEL, UI_LABELS } from "../../labels";
import { NOT_IN_VIEW } from "../../model/analysis";
import type { Assignment, Detection, Side } from "../../model/analysis";
import { Badge, Button, Card, HelpTip, IconButton, SectionHeading, cx } from "../../ui";
import { IconAlert, IconCheck, IconChevronLeft, IconChevronRight, IconEdit } from "../../ui/icons";
import { cropRect } from "./crop";
import type { CropRect } from "./crop";
import { selectionGuide } from "./guide";
import type { GuideStep } from "./guide";

/** The picture the candidate tiles are cut from. */
export interface CropSource {
  /** Draws the square `rect` of the shown frame into a `size`×`size` canvas. */
  draw: (ctx: CanvasRenderingContext2D, rect: CropRect, size: number) => void;
  /** Changes whenever another frame is shown. */
  version: unknown;
}

interface LayoutProps {
  title: ReactNode;
  picks: Assignment;
  onPick?: (next: Assignment) => void;
  detections: Detection[];
  frame: { width: number; height: number };
  stage: (boxes: ReactNode) => ReactNode;
  /** null while the frame is not presented yet (tiles stay dark). */
  source: CropSource | null;
  names: Record<Side, string>;
  onRename?: (side: Side, name: string) => void;
  candidateLabel: string;
  onPrev?: () => void;
  onNext?: () => void;
  onConfirm?: () => void;
  problem?: string | null;
  /** Extra navigation (e.g. frame steps) next to the candidate arrows. */
  navExtra?: ReactNode;
  /** Extra content in the side panel (earlier selections...). */
  extra?: ReactNode;
  /** "Maç ayarları" card under the people on the frame. */
  settings?: ReactNode;
  confirmLabel?: string;
  busy?: boolean;
  /** Offer "not in the picture on this frame" for a corner (corrections on close-ups). */
  allowNotInView?: boolean;
}

const CROP_PX = 320;
const MAX_NAME = 40;

function CropCanvas({ source, rect }: { source: CropSource | null; rect: CropRect }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { x, y, size } = rect;
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    source?.draw(ctx, { x, y, size }, canvas.width);
  }, [source, x, y, size]);
  return <canvas ref={ref} className="crop" width={CROP_PX} height={CROP_PX} aria-hidden="true" />;
}

/** Name shown as text; a click (or Enter) edits it in place, Enter saves, Esc cancels. */
function InlineName({ value, label, editLabel, onSave }: {
  value: string;
  label: string;
  editLabel: string;
  onSave?: (value: string) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (draft === null && refocus.current) {
      refocus.current = false;
      buttonRef.current?.focus();
    }
  }, [draft]);

  if (!onSave) return <span className="inline-name inline-name--static">{value}</span>;
  if (draft === null) {
    return (
      <button ref={buttonRef} type="button" className="inline-name" aria-label={editLabel} onClick={() => setDraft(value)}>
        <span className="inline-name__text">{value}</span>
        <IconEdit size={16} className="inline-name__icon" />
      </button>
    );
  }
  const finish = (save: boolean) => {
    const name = draft.trim();
    if (save && name) onSave(name);
    setDraft(null);
  };
  return (
    <input className="inline-name__input" value={draft} maxLength={MAX_NAME} autoFocus aria-label={label}
           onChange={(e) => setDraft(e.target.value)} onBlur={() => finish(true)}
           onKeyDown={(e) => {
             if (e.key !== "Enter" && e.key !== "Escape") return;
             e.preventDefault();
             refocus.current = true;
             finish(e.key === "Enter");
           }} />
  );
}

/**
 * Numbered guide: 1. red corner, 2. blue corner, 3. names and confirm, each
 * with its state. The first two steps carry their corner's colour; the third
 * is black, so red on this screen only ever means the red corner.
 */
function Guide({ steps }: { steps: GuideStep[] }) {
  return (
    <ol className="guide" aria-label={L.guide.label}>
      {steps.map((step, i) => (
        <li key={step.id} className={cx("guide__step", `guide__step--${step.id}`, `is-${step.state}`)}
            aria-current={step.state === "active" ? "step" : undefined}>
          <span className="guide__num num">{step.state === "done" ? <IconCheck size={16} /> : i + 1}</span>
          <span className="guide__text">
            <span className="guide__title">{L.guide.steps[step.id].title}</span>
            <span className="guide__hint">{L.guide.steps[step.id].hint}</span>
          </span>
          <span className="guide__state">{L.guide.state[step.state]}</span>
        </li>
      ))}
    </ol>
  );
}

/**
 * Pick the red and then the blue corner on a frame: by clicking a box on the
 * frame or one of the large candidate tiles below it (the keyboard path).
 */
export function SelectionLayout(p: LayoutProps) {
  const titleId = useId();
  const peopleId = useId();
  const next: Side | null = p.picks.red === null ? "red" : p.picks.blue === null ? "blue" : null;
  const sideOf = (id: string): Side | null =>
    p.picks.red === id ? "red" : p.picks.blue === id ? "blue" : null;

  const toggle = (id: string) => {
    if (!p.onPick) return;
    const side = sideOf(id);
    if (side) p.onPick({ ...p.picks, [side]: null });
    else if (next) p.onPick({ ...p.picks, [next]: id });
  };

  // People numbered left to right (boxes, tiles and corner rows use the same numbers).
  const ordered = [...p.detections].sort((a, b) => a.x1 - b.x1);
  const number = new Map(ordered.map((d, i) => [d.personId, i + 1]));
  const personName = (id: string) => L.person(number.get(id) ?? 0);
  const confidence = (d: Detection) => Math.round(d.confidence * 100);
  const aria = (d: Detection) => {
    const side = sideOf(d.personId);
    return L.personAria(personName(d.personId), confidence(d), side ? SIDE_LABEL[side] : null);
  };

  // Larger boxes first so a smaller box overlapping a larger one stays clickable on top.
  // The tiles below are the keyboard path, so the boxes are left out of the tab order.
  const area = (d: Detection) => (d.x2 - d.x1) * (d.y2 - d.y1);
  const boxes = [...p.detections].sort((a, b) => area(b) - area(a)).map((d) => {
    const side = sideOf(d.personId);
    const style = {
      left: `${(d.x1 / p.frame.width) * 100}%`,
      top: `${(d.y1 / p.frame.height) * 100}%`,
      width: `${((d.x2 - d.x1) / p.frame.width) * 100}%`,
      height: `${((d.y2 - d.y1) / p.frame.height) * 100}%`,
    };
    return (
      <button key={d.personId} type="button" tabIndex={-1} style={style}
              className={cx("pick", side && `pick--${side}`, !side && next && `pick--next-${next}`)}
              aria-pressed={side !== null} aria-label={aria(d)} disabled={!side && !next}
              onClick={() => toggle(d.personId)}>
        <span className="pick__tag">
          {side ? SIDE_LABEL[side] : personName(d.personId)} <span className="num">%{confidence(d)}</span>
        </span>
      </button>
    );
  });

  const ready = p.picks.red !== null && p.picks.blue !== null &&
    !(p.picks.red === NOT_IN_VIEW && p.picks.blue === NOT_IN_VIEW);

  return (
    <div className="select">
      <Guide steps={selectionGuide(p.picks, ready)} />
      <section className="select__main" aria-labelledby={titleId}>
        <div className="select__head">
          <h1 id={titleId} className="select__title">{p.title}</h1>
          <div className="select__nav">
            <IconButton label={L.prevCandidate} icon={<IconChevronLeft />} variant="secondary" onClick={p.onPrev}
                        disabled={!p.onPrev} />
            <span className="num select__candidate">{p.candidateLabel}</span>
            <IconButton label={L.nextCandidate} icon={<IconChevronRight />} variant="secondary" onClick={p.onNext}
                        disabled={!p.onNext} />
            {p.navExtra}
          </div>
        </div>
        {p.stage(boxes)}
        <p className="select__hint">{L.hint}</p>
        {ordered.length > 0 && (
          <section className="candidates" aria-labelledby={peopleId}>
            <SectionHeading id={peopleId} level={3} title={L.peopleTitle} description={L.peopleDescription}
                            aside={<HelpTip label={UI_LABELS.help(L.confidenceTerm)} align="start">{L.confidenceHelp}</HelpTip>} />
            <ul className="candidates__grid">
              {ordered.map((d) => {
                const side = sideOf(d.personId);
                return (
                  <li key={d.personId}>
                    <button type="button" className={cx("candidate", side && `candidate--${side}`)}
                            aria-pressed={side !== null} aria-label={aria(d)} disabled={!side && !next}
                            onClick={() => toggle(d.personId)}>
                      <span className="candidate__picture">
                        <CropCanvas source={p.source} rect={cropRect(d, p.frame)} />
                        {side && <Badge tone={side} solid className="candidate__badge">{SIDE_LABEL[side]}</Badge>}
                      </span>
                      <span className="candidate__caption">
                        <span>{personName(d.personId)}</span>
                        <span className="num">%{confidence(d)}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
        {p.settings}
      </section>

      <Card tag="aside" className="select__side" aria-label={L.cornersLabel}>
        <SectionHeading level={3} title={L.cornersTitle} description={L.cornersDescription} />
        <ol className="corners">
          {(["red", "blue"] as const).map((side, i) => {
            const pick = p.picks[side];
            const absent = pick === NOT_IN_VIEW;
            const chosen = pick !== null && !absent ? p.detections.find((d) => d.personId === pick) : undefined;
            const active = next === side;
            const corner = SIDE_LABEL[side];
            const status = absent ? L.stateAbsent : chosen ? L.stateChosen(personName(chosen.personId))
              : active ? L.stateActive : L.stateNext;
            return (
              <li key={side} className={cx("corner", `corner--${side}`, active && "is-active", pick !== null && "is-done")}>
                <span className="corner__thumb">
                  {chosen ? <CropCanvas source={p.source} rect={cropRect(chosen, p.frame)} /> : <span className="num">{i + 1}</span>}
                </span>
                <div className="corner__body">
                  <Badge tone={side}>{L.corner(corner)}</Badge>
                  <InlineName value={p.names[side]} label={L.nameLabel(corner)} editLabel={L.editName(corner, p.names[side])}
                              onSave={p.onRename ? (name) => p.onRename?.(side, name) : undefined} />
                  <p className="corner__status">{status}</p>
                  {p.allowNotInView && p.onPick && (active || absent) && (
                    <button type="button" className="linkbtn corner__absent"
                            onClick={() => p.onPick?.({ ...p.picks, [side]: absent ? null : NOT_IN_VIEW })}>
                      {absent ? L.undo : L.notInView}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
        {p.extra}
        {p.problem && (
          <div className="alert" role="alert"><IconAlert /><span>{p.problem}</span></div>
        )}
        <div className="select__actions">
          <Button variant="primary" disabled={!ready || !p.onConfirm || p.busy} onClick={p.onConfirm}>
            {p.busy ? L.sending : (p.confirmLabel ?? L.confirmDemo)}
          </Button>
          <Button disabled={!p.onPick || (!p.picks.red && !p.picks.blue)}
                  onClick={() => p.onPick?.({ red: null, blue: null })}>
            {L.reset}
          </Button>
        </div>
      </Card>
    </div>
  );
}
