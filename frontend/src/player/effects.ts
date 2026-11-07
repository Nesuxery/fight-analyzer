/**
 * Which event effects are visible at a video time, and how strongly.
 *
 * Durations come from shared/overlay-style.json (via the generated
 * OVERLAY_STYLE) and are measured in video time relative to the event's peak,
 * so pausing freezes an effect and seeking back shows it again. The MP4 export
 * uses the same rules (backend/fight_analyzer/export/frames.py, effects_at).
 */
import type { FightEvent } from "../contracts/generated";
// explicit extension: this module also runs in the Node unit tests
import { OVERLAY_STYLE } from "../contracts/overlayStyle.ts";

const STRIKES = new Set(["punch", "kick", "knee"]);
const MAJOR = new Set(["knockdown", "takedown"]);

export interface StrikeFlash { event: FightEvent; strength: number }
export interface ContactRing { event: FightEvent; strength: number; labelled: boolean }
export interface MajorWarning { event: FightEvent; strength: number }
export interface Effects { flashes: StrikeFlash[]; rings: ContactRing[]; warnings: MajorWarning[] }

export const eventPeakS = (e: FightEvent): number => (e.peak_ms ?? e.start_ms) / 1000;

/** Events in excluded parts (`excludedIds`) get no effect. */
export function effectsAt(events: readonly FightEvent[], tS: number,
                          excludedIds: ReadonlySet<string> = new Set()): Effects {
  const { strike_flash: flash, contact_ring: ring, major_warning: major } = OVERLAY_STYLE;
  const out: Effects = { flashes: [], rings: [], warnings: [] };
  for (const e of events) {
    if (excludedIds.has(e.event_id)) continue;
    const age = tS - eventPeakS(e);
    if (STRIKES.has(e.type)) {
      if (age >= -flash.before_s && age <= flash.after_s) {
        out.flashes.push({ event: e, strength: age <= 0 ? 1 : 1 - age / flash.after_s });
      }
      if (e.possible_contact && e.location && age >= 0 && age <= ring.after_s) {
        out.rings.push({ event: e, strength: 1 - age / ring.after_s, labelled: false });
      }
    } else if (MAJOR.has(e.type) && age >= 0 && age <= major.after_s) {
      const hold = major.after_s - major.fade_s;
      out.warnings.push({ event: e, strength: age <= hold ? 1 : (major.after_s - age) / major.fade_s });
    }
  }
  // only the most recent ring carries the "olası temas" text, so labels never pile up
  let latest: ContactRing | null = null;
  for (const r of out.rings) if (!latest || eventPeakS(r.event) > eventPeakS(latest.event)) latest = r;
  if (latest) latest.labelled = true;
  return out;
}
