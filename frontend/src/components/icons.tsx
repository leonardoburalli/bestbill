import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Base({ size = 20, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  )
}

export const CheckIcon = (p: IconProps) => (
  <Base {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></Base>
)
export const ArrowLeftIcon = (p: IconProps) => (
  <Base {...p}><path d="M19 12H5M11 6l-6 6 6 6" /></Base>
)
export const ArrowRightIcon = (p: IconProps) => (
  <Base {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Base>
)
export const ChevronDownIcon = (p: IconProps) => (
  <Base {...p}><path d="M6 9l6 6 6-6" /></Base>
)
export const DownloadIcon = (p: IconProps) => (
  <Base {...p}><path d="M12 4v11M7 11l5 5 5-5M5 20h14" /></Base>
)
export const ExternalIcon = (p: IconProps) => (
  <Base {...p}><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></Base>
)
export const InfoIcon = (p: IconProps) => (
  <Base {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></Base>
)
export const AlertIcon = (p: IconProps) => (
  <Base {...p}><path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18h.01" /></Base>
)
export const UploadIcon = (p: IconProps) => (
  <Base {...p}><path d="M12 16V5M7 9l5-5 5 5M5 20h14" /></Base>
)
export const ClipboardIcon = (p: IconProps) => (
  <Base {...p}><rect x="6" y="5" width="12" height="16" rx="2" /><path d="M9 5V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M9 11h6M9 15h6" /></Base>
)
export const HomeIcon = (p: IconProps) => (
  <Base {...p}><path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z" /></Base>
)
export const SearchIcon = (p: IconProps) => (
  <Base {...p}><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.2-4.2" /></Base>
)
export const CloseIcon = (p: IconProps) => (
  <Base {...p}><path d="M6 6l12 12M18 6L6 18" /></Base>
)
export const RefreshIcon = (p: IconProps) => (
  <Base {...p}><path d="M20 11a8 8 0 1 0-2.3 6.3M20 4v7h-7" /></Base>
)
export const TrophyIcon = (p: IconProps) => (
  <Base {...p}><path d="M8 4h8v6a4 4 0 0 1-8 0zM8 6H4v2a4 4 0 0 0 4 4M16 6h4v2a4 4 0 0 1-4 4M12 14v4M8 20h8" /></Base>
)

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <rect width="64" height="64" rx="14" fill="#1d5a44" />
      <path d="M18 12h28v40l-5-3.5-4.5 3.5-4.5-3.5-4.5 3.5-4.5-3.5-5 3.5z" fill="#fffdf8" />
      <path d="M25 30l5 5 10-11" fill="none" stroke="#1d5a44" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
