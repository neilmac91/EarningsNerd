export default function EinsteinLogo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="65%">
          <stop offset="0%" stopColor="#1d4ed8" stopOpacity="0.35" />
          <stop offset="60%" stopColor="#1d4ed8" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#0f172a" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="badge" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="50%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
        <linearGradient id="arrow" x1="20%" y1="80%" x2="80%" y2="20%">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#f472b6" />
        </linearGradient>
      </defs>

      <circle cx="32" cy="32" r="24" fill="url(#badge)" />
      <circle cx="32" cy="32" r="24" fill="url(#glow)" />
      <circle cx="32" cy="32" r="23" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />

      {/* upward earnings arrow */}
      <path
        d="M18 38l11.5-11.5 7.5 7.5L46 23"
        fill="none"
        stroke="url(#arrow)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M41 23h7v7"
        fill="none"
        stroke="url(#arrow)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* nerd glasses */}
      <g transform="translate(13,8)">
        <circle cx="14" cy="28" r="6.5" stroke="rgba(15,23,42,0.85)" strokeWidth="2.4" fill="rgba(15,23,42,0.15)" />
        <circle cx="30" cy="28" r="6.5" stroke="rgba(15,23,42,0.85)" strokeWidth="2.4" fill="rgba(15,23,42,0.15)" />
        <rect
          x="20"
          y="26.8"
          width="4"
          height="2.4"
          rx="1.2"
          fill="rgba(15,23,42,0.85)"
        />
        <path
          d="M7.5 28c-1.5 0-2.5 0.9-2.5 2.3"
          stroke="rgba(15,23,42,0.5)"
          strokeWidth="2"
          strokeLinecap="round"
          fill="none"
        />
        <path
          d="M36.5 28c1.5 0 2.5 0.9 2.5 2.3"
          stroke="rgba(15,23,42,0.5)"
          strokeWidth="2"
          strokeLinecap="round"
          fill="none"
        />
      </g>

      {/* spark */}
      <path
        d="M44 14l1.2 2.8 2.8 1.2-2.8 1.2-1.2 2.8-1.2-2.8-2.8-1.2 2.8-1.2 1.2-2.8z"
        fill="rgba(255,255,255,0.75)"
      />
    </svg>
  )
}

