import { cx } from "./cx";

const CENTER = 200;
const RADII = [58, 104, 150, 196];

/** Corner points of a regular octagon with flat top and bottom. */
function octagon(radius: number): string {
  return Array.from({ length: 8 }, (_, k) => {
    const angle = Math.PI / 8 + (k * Math.PI) / 4;
    return `${(CENTER + radius * Math.cos(angle)).toFixed(1)},${(CENTER + radius * Math.sin(angle)).toFixed(1)}`;
  }).join(" ");
}

/**
 * Faint concentric octagon lines for dark bands. Decoration only: drawn in the
 * text colour of the band at --band-pattern-opacity (at most 6 %).
 */
export function OctagonPattern({ className }: { className?: string }) {
  return (
    <svg className={cx("octpattern", className)} viewBox="0 0 400 400" fill="none" stroke="currentColor"
         strokeWidth="1.5" aria-hidden="true" focusable="false">
      {RADII.map((r) => <polygon key={r} points={octagon(r)} vectorEffect="non-scaling-stroke" />)}
    </svg>
  );
}
