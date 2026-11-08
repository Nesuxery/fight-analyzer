import { SIDE_LABEL, UI_LABELS, formatNumber } from "../labels";
import { cx } from "./cx";
import { statPairShares } from "./statPairShares";

/**
 * Mirrored comparison row: red value and bar on the left, the label in the
 * middle, blue on the right. `uncertain` shows low-confidence data as such
 * instead of presenting it as exact.
 */
export function StatPair({ label, red, blue, max, format = (v) => formatNumber(v), uncertain = false }: {
  label: string;
  red: number | null;
  blue: number | null;
  /** Fixed scale for the bars; default: the larger value. */
  max?: number;
  format?: (value: number) => string;
  uncertain?: boolean;
}) {
  const shares = statPairShares(red, blue, max);
  const text = (v: number | null) => (v === null ? UI_LABELS.noValue : format(v));
  return (
    <div className={cx("statpair", uncertain && "is-uncertain")}>
      <span className="sr-only">
        {label}: {SIDE_LABEL.red} {text(red)}, {SIDE_LABEL.blue} {text(blue)}{uncertain ? ` (${UI_LABELS.uncertain})` : ""}
      </span>
      <span className="statpair__value statpair__value--red" aria-hidden="true">{text(red)}</span>
      <span className="statpair__bar statpair__bar--red" aria-hidden="true">
        <span style={{ transform: `scaleX(${shares.red})` }} />
      </span>
      <span className="statpair__label" aria-hidden="true">
        {label}
        {uncertain && <span className="statpair__note">{UI_LABELS.uncertain}</span>}
      </span>
      <span className="statpair__bar statpair__bar--blue" aria-hidden="true">
        <span style={{ transform: `scaleX(${shares.blue})` }} />
      </span>
      <span className="statpair__value statpair__value--blue" aria-hidden="true">{text(blue)}</span>
    </div>
  );
}
