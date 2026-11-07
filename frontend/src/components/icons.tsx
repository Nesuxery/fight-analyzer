import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 18, children, ...rest }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      {children}
    </svg>
  );
}

export const IconPlay = (p: IconProps) => (
  <Icon {...p}><path d="M7 4.5v15l12.5-7.5z" fill="currentColor" stroke="none" /></Icon>
);
export const IconPause = (p: IconProps) => (
  <Icon {...p}><path d="M7 4.5h3.5v15H7zM13.5 4.5H17v15h-3.5z" fill="currentColor" stroke="none" /></Icon>
);
export const IconBack = (p: IconProps) => (
  <Icon {...p}><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" /></Icon>
);
export const IconForward = (p: IconProps) => (
  <Icon {...p}><path d="M13 7l5 5-5 5M6 7l5 5-5 5" /></Icon>
);
export const IconFramePrev = (p: IconProps) => (
  <Icon {...p}><path d="M15 6l-6 6 6 6M6 6v12" /></Icon>
);
export const IconFrameNext = (p: IconProps) => (
  <Icon {...p}><path d="M9 6l6 6-6 6M18 6v12" /></Icon>
);
export const IconChevronLeft = (p: IconProps) => <Icon {...p}><path d="M15 6l-6 6 6 6" /></Icon>;
export const IconChevronRight = (p: IconProps) => <Icon {...p}><path d="M9 6l6 6-6 6" /></Icon>;
export const IconEdit = (p: IconProps) => (
  <Icon {...p}><path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" /></Icon>
);
export const IconSwap = (p: IconProps) => (
  <Icon {...p}><path d="M7 7h12l-3-3M17 17H5l3 3" /></Icon>
);
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
  <Icon {...p}><path d="M12 8v5M12 16.5v.5M10.3 3.9L2.6 17.5A2 2 0 004.3 20.5h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" /></Icon>
);
export const IconFilm = (p: IconProps) => (
  <Icon {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M7 5v14M17 5v14M3 9.5h4M3 14.5h4M17 9.5h4M17 14.5h4" /></Icon>
);
export const IconClose = (p: IconProps) => <Icon {...p}><path d="M6 6l12 12M18 6L6 18" /></Icon>;
