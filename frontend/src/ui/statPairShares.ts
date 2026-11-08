/**
 * Bar lengths (0..1) of a mirrored red/blue comparison. By default the larger
 * value fills its side and the other is in proportion; `max` fixes the scale
 * (e.g. a percentage out of 100). Missing or non-numeric values and an empty
 * scale give no bar.
 */
export function statPairShares(red: number | null, blue: number | null, max?: number): { red: number; blue: number } {
  const valid = (v: number | null): v is number => v !== null && Number.isFinite(v);
  const top = max ?? Math.max(0, ...[red, blue].filter(valid));
  if (!(top > 0)) return { red: 0, blue: 0 };
  const share = (v: number | null) => (valid(v) ? Math.min(1, Math.max(0, v / top)) : 0);
  return { red: share(red), blue: share(blue) };
}
