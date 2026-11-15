import { SCOPE_LABELS, UI_LABELS } from "../../labels";
import { roundNear } from "../../model/scope";
import type { RoundSpan, Scope, ScopeKind } from "../../model/scope";
import { HelpTip, SegmentedControl } from "../../ui";

const L = SCOPE_LABELS;

/**
 * Which stretch of the bout the side panels' numbers belong to: up to the
 * playhead, one round, or the whole bout. One control for both panels, so the
 * two sides are always compared over the same time.
 */
export function ScopeBar({ scope, onScope, rounds, frame, range }: {
  scope: Scope;
  onScope: (scope: Scope) => void;
  rounds: readonly RoundSpan[];
  frame: number;
  /** The range in effect as text (e.g. "00:10 – 05:10"); null when the scope has no frames. */
  range: string | null;
}) {
  const hasRounds = rounds.length > 0;
  const options = [
    { value: "playhead" as const, label: L.playhead },
    ...(hasRounds ? [{ value: "round" as const, label: L.round }] : []),
    { value: "bout" as const, label: L.bout },
  ];
  const pick = (kind: ScopeKind) => {
    if (kind === "round") onScope({ kind, index: roundNear(rounds, frame) ?? rounds[0]!.index });
    else onScope({ kind });
  };
  return (
    <div className="scopebar" role="group" aria-label={L.group}>
      <span className="scopebar__label">
        {L.label}
        <HelpTip label={UI_LABELS.help(L.label)} align="start">{L.help}</HelpTip>
      </span>
      <SegmentedControl label={L.group} options={options} value={scope.kind} onChange={pick} />
      {scope.kind === "round" && (
        <label className="scopebar__round">
          <span className="sr-only">{L.roundPick}</span>
          <select value={scope.index} onChange={(e) => onScope({ kind: "round", index: Number(e.target.value) })}>
            {[...rounds].sort((a, b) => a.index - b.index).map((r) => (
              <option key={r.index} value={r.index}>{L.roundOption(r.index)}</option>
            ))}
          </select>
        </label>
      )}
      {range && <span className="scopebar__range num">{range}</span>}
      {!hasRounds && <span className="scopebar__hint">{L.noRounds}</span>}
    </div>
  );
}
