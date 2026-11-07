/* Generated from shared/overlay-style.json by `npm run gen:types`. Do not edit by hand. */
/** Overlay style shared with the MP4 export (backend/fight_analyzer/export/style.py). */
export const OVERLAY_STYLE = {
  "description": "Analysis overlay style shared by the browser (frontend/src/player/overlay.ts) and the MP4 export (backend/fight_analyzer/export/render.py), so both show the same effects at the same video times. Times are seconds of video time relative to the event moment (peak), never wall-clock time.",
  "kp_min_conf": 0.5,
  "colors": {
    "red": "#ff2e4d",
    "blue": "#19d6f0",
    "other": "#9aa6bd",
    "amber": "#ffb020",
    "warning": "#ffd21f"
  },
  "strike_flash": {
    "before_s": 0.06,
    "after_s": 0.3
  },
  "contact_ring": {
    "after_s": 0.35,
    "radius_px": 9
  },
  "major_warning": {
    "after_s": 2,
    "fade_s": 0.3
  },
  "limbs": {
    "left_hand": [
      5,
      7,
      9
    ],
    "right_hand": [
      6,
      8,
      10
    ],
    "left_foot": [
      11,
      13,
      15
    ],
    "right_foot": [
      12,
      14,
      16
    ],
    "left_knee": [
      11,
      13
    ],
    "right_knee": [
      12,
      14
    ]
  }
} as const;
