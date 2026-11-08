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
/** Brand mark: a plain octagon outline in the text colour. */
export const IconOctagon = (p: IconProps) => (
  <Icon {...p}><path d="M8.7 3h6.6L21 8.7v6.6L15.3 21H8.7L3 15.3V8.7z" /></Icon>
);
