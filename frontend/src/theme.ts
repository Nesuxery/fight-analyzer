import type { Side } from "./model/analysis";

/** Canvas colours (CSS uses the matching custom properties in tokens.css). */
export const COLORS = {
  red: "#ff2e4d",
  cyan: "#19d6f0",
  amber: "#ffb020",
  neutral: "#c9d4ea",
  text: "#eef2fa",
} as const;

export const SIDE_COLOR: Record<Side, string> = { red: COLORS.red, blue: COLORS.cyan };

export const SIDE_LABEL: Record<Side, string> = { red: "Kırmızı", blue: "Mavi" };
