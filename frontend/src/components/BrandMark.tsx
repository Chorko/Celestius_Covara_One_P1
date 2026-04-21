import { useId } from "react";

interface BrandMarkProps {
  size?: number;
  className?: string;
}

export default function BrandMark({ size = 36, className = "" }: BrandMarkProps) {
  const uniqueId = useId().replace(/:/g, "");
  const baseGradientId = `covara-brand-base-${uniqueId}`;
  const accentGradientId = `covara-brand-accent-${uniqueId}`;

  return (
    <span
      className={["brand-mark", className].filter(Boolean).join(" ")}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 64 64" fill="none" focusable="false">
        <defs>
          <linearGradient id={baseGradientId} x1="8" y1="6" x2="56" y2="58" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#0F3127" />
            <stop offset="0.55" stopColor="#1F6B54" />
            <stop offset="1" stopColor="#2EA67F" />
          </linearGradient>
          <linearGradient id={accentGradientId} x1="21" y1="28" x2="44" y2="43" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#B8FFE4" />
            <stop offset="1" stopColor="#6FD2FF" />
          </linearGradient>
        </defs>

        <rect x="4" y="4" width="56" height="56" rx="18" fill={`url(#${baseGradientId})`} />
        <rect x="14" y="14" width="36" height="36" rx="12" stroke="rgba(187, 255, 229, 0.82)" strokeWidth="2.4" />
        <path
          d="M21 38.5L30 29.5L42.5 42"
          stroke={`url(#${accentGradientId})`}
          strokeWidth="4.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M21.5 26.5H33.5" stroke="rgba(180, 248, 223, 0.95)" strokeWidth="3.8" strokeLinecap="round" />
        <circle cx="42.4" cy="22.2" r="4.5" fill="#52C3FF" />
        <circle cx="42.4" cy="22.2" r="2.2" fill="#EAFBFF" />
      </svg>
    </span>
  );
}
