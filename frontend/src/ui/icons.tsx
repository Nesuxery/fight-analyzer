import type { ReactNode, SVGProps } from "react";

/** The one icon set of the app: 24-unit grid, drawn at 16 or 20 px with a 1.5 px line. */
export type IconSize = 16 | 20;
export type IconProps = Omit<SVGProps<SVGSVGElement>, "width" | "height" | "children"> & { size?: IconSize };

function Icon({ size = 20, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         // 1.5 px on screen at either size
         strokeWidth={(1.5 * 24) / size} strokeLinecap="round" strokeLinejoin="round"
         aria-hidden="true" focusable="false" {...rest}>
      {children}
    </svg>
  );
}

const filled = { fill: "currentColor", stroke: "none" } as const;

export const IconPlay = (p: IconProps) => <Icon {...p}><path d="M7 4.5v15l12.5-7.5z" {...filled} /></Icon>;
export const IconPause = (p: IconProps) => (
  <Icon {...p}><path d="M7 4.5h3.5v15H7zM13.5 4.5H17v15h-3.5z" {...filled} /></Icon>
);
export const IconBack = (p: IconProps) => <Icon {...p}><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" /></Icon>;
export const IconForward = (p: IconProps) => <Icon {...p}><path d="M13 7l5 5-5 5M6 7l5 5-5 5" /></Icon>;
export const IconFramePrev = (p: IconProps) => <Icon {...p}><path d="M15 6l-6 6 6 6M6 6v12" /></Icon>;
export const IconFrameNext = (p: IconProps) => <Icon {...p}><path d="M9 6l6 6-6 6M18 6v12" /></Icon>;
export const IconChevronLeft = (p: IconProps) => <Icon {...p}><path d="M15 6l-6 6 6 6" /></Icon>;
export const IconChevronRight = (p: IconProps) => <Icon {...p}><path d="M9 6l6 6-6 6" /></Icon>;
export const IconChevronDown = (p: IconProps) => <Icon {...p}><path d="M6 9l6 6 6-6" /></Icon>;
export const IconEdit = (p: IconProps) => <Icon {...p}><path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" /></Icon>;
export const IconSwap = (p: IconProps) => <Icon {...p}><path d="M7 7h12l-3-3M17 17H5l3 3" /></Icon>;
export const IconTarget = (p: IconProps) => (
  <Icon {...p}><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /></Icon>
);
export const IconUpload = (p: IconProps) => (
  <Icon {...p}><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" /></Icon>
);
export const IconDownload = (p: IconProps) => (
  <Icon {...p}><path d="M12 4v12M7 11l5 5 5-5M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" /></Icon>
);
export const IconCheck = (p: IconProps) => <Icon {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></Icon>;
export const IconAlert = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 8.5v4.5M12 16.5v.01M10.3 3.9L2.6 17.5A2 2 0 004.3 20.5h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
  </Icon>
);
export const IconFilm = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M7 5v14M17 5v14M3 9.5h4M3 14.5h4M17 9.5h4M17 14.5h4" />
  </Icon>
);
export const IconClose = (p: IconProps) => <Icon {...p}><path d="M6 6l12 12M18 6L6 18" /></Icon>;
/** Step not started yet. */
export const IconCircle = (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="8" /></Icon>;
/** Cancelled / stopped. */
export const IconStop = (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="8" /><path d="M8 12h8" /></Icon>;
/** Work in progress; spins with the `icon-spin` class (not with reduced motion). */
export const IconSpinner = (p: IconProps) => (
  <Icon {...p}><path d="M12 4a8 8 0 018 8" /><circle cx="12" cy="12" r="8" opacity="0.25" /></Icon>
);
/** Brand mark: a plain octagon; the top bar fills it with the brand red (.brand__mark). */
export const IconOctagon = (p: IconProps) => (
  <Icon {...p}><path d="M8.7 3h6.6L21 8.7v6.6L15.3 21H8.7L3 15.3V8.7z" /></Icon>
);
/** "?" of HelpTip. */
export const IconHelp = (p: IconProps) => (
  <Icon {...p}><circle cx="12" cy="12" r="8.5" /><path d="M9.7 9.7a2.4 2.4 0 114 1.8c-.9.7-1.7 1.2-1.7 2.4M12 16.8v.01" /></Icon>
);
export const IconArrowRight = (p: IconProps) => <Icon {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>;
/** Runs on this computer; also the "Sistem" theme (follows the computer's setting). */
export const IconMonitor = (p: IconProps) => (
  <Icon {...p}><rect x="3" y="4.5" width="18" height="12" rx="2" /><path d="M8.5 20h7M12 16.5V20" /></Icon>
);
/** Light theme. */
export const IconSun = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
  </Icon>
);
/** Dark theme. */
export const IconMoon = (p: IconProps) => (
  <Icon {...p}><path d="M20 14.2A8 8 0 019.8 4a8 8 0 1010.2 10.2z" /></Icon>
);
/** No internet needed. */
export const IconWifiOff = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 4l16 16M8.6 15.6a5 5 0 016.2-.5M5.3 12.2a9.6 9.6 0 013.3-2.1M12.4 9.1a9.6 9.6 0 016.3 3.1M2.5 8.6a14 14 0 013-2.2M9.6 5.2A14 14 0 0121.5 8.6M12 19.3v.01" />
  </Icon>
);
/** The video does not leave the computer. */
export const IconLock = (p: IconProps) => (
  <Icon {...p}><rect x="5" y="10.5" width="14" height="9.5" rx="2" /><path d="M8 10.5V8a4 4 0 018 0v2.5" /></Icon>
);
/** Processing. */
export const IconCpu = (p: IconProps) => (
  <Icon {...p}>
    <rect x="7" y="7" width="10" height="10" rx="1.5" />
    <path d="M10 3.5V7M14 3.5V7M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5" />
  </Icon>
);
/** The two fighters. */
export const IconUsers = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="8.5" cy="8" r="3" /><path d="M2.5 19.5a6 6 0 0112 0" />
    <circle cx="16.8" cy="9" r="2.4" /><path d="M17 14a4.8 4.8 0 014.5 5.5" />
  </Icon>
);
/** Result and scorecards. */
export const IconScorecard = (p: IconProps) => (
  <Icon {...p}><rect x="5" y="4.5" width="14" height="16" rx="2" /><path d="M9.5 3.5h5v2h-5zM8.5 10.5h7M8.5 14h7M8.5 17.5h4" /></Icon>
);
/** Metric group: striking. */
export const IconZap = (p: IconProps) => <Icon {...p}><path d="M13 3L5 13.5h6l-1 7.5 8-10.5h-6z" /></Icon>;
/** Metric group: movement and pressure. */
export const IconMove = (p: IconProps) => <Icon {...p}><path d="M4 12h16M8 8l-4 4 4 4M16 8l4 4-4 4" /></Icon>;
/** Metric group: control (time on top). */
export const IconTimer = (p: IconProps) => (
  <Icon {...p}><circle cx="12" cy="13.5" r="7" /><path d="M12 10v3.5l2.4 1.4M9.5 3.5h5" /></Icon>
);
/** Metric group: data quality. */
export const IconSignal = (p: IconProps) => <Icon {...p}><path d="M5 19.5v-3M10 19.5v-7M15 19.5v-11M20 19.5V4.5" /></Icon>;
