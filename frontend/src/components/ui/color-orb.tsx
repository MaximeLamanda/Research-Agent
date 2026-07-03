"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface ColorOrbProps {
  dimension?: string;
  className?: string;
  spinDuration?: number;
}

export function ColorOrb({
  dimension = "96px",
  className,
  spinDuration = 20,
}: ColorOrbProps) {
  const palette = {
    base: "oklch(95% 0.02 264.695)",
    accent1: "oklch(75% 0.15 350)",
    accent2: "oklch(80% 0.12 200)",
    accent3: "oklch(78% 0.14 280)",
  };

  const dimValue = parseInt(dimension.replace("px", ""), 10);
  const blurStrength = Math.max(dimValue * 0.015, 4);
  const contrastStrength = Math.max(dimValue * 0.008, 1.5);
  const pixelDot = Math.max(dimValue * 0.008, 0.1);
  const shadowRange = Math.max(dimValue * 0.008, 2);
  const maskRadius = dimValue < 100 ? "15%" : "25%";

  return (
    <div
      className={cn("color-orb", className)}
      style={{
        width: dimension,
        height: dimension,
        ["--base" as string]: palette.base,
        ["--accent1" as string]: palette.accent1,
        ["--accent2" as string]: palette.accent2,
        ["--accent3" as string]: palette.accent3,
        ["--spin-duration" as string]: `${spinDuration}s`,
        ["--blur" as string]: `${blurStrength}px`,
        ["--contrast" as string]: contrastStrength,
        ["--dot" as string]: `${pixelDot}px`,
        ["--shadow" as string]: `${shadowRange}px`,
        ["--mask" as string]: maskRadius,
      }}
    >
      <style>{`
        @property --angle {
          syntax: "<angle>";
          inherits: false;
          initial-value: 0deg;
        }
        .color-orb {
          display: grid;
          grid-template-areas: "stack";
          overflow: hidden;
          border-radius: 50%;
          position: relative;
          transform: scale(1.1);
        }
        .color-orb::before,
        .color-orb::after {
          content: "";
          display: block;
          grid-area: stack;
          width: 100%;
          height: 100%;
          border-radius: 50%;
        }
        .color-orb::before {
          background:
            conic-gradient(from calc(var(--angle) * 2) at 25% 70%, var(--accent3), transparent 20% 80%, var(--accent3)),
            conic-gradient(from calc(var(--angle) * 2) at 45% 75%, var(--accent2), transparent 30% 60%, var(--accent2)),
            conic-gradient(from calc(var(--angle) * -3) at 80% 20%, var(--accent1), transparent 40% 60%, var(--accent1)),
            conic-gradient(from calc(var(--angle) * 2) at 15% 5%, var(--accent2), transparent 10% 90%, var(--accent2)),
            conic-gradient(from calc(var(--angle) * 1) at 20% 80%, var(--accent1), transparent 10% 90%, var(--accent1)),
            conic-gradient(from calc(var(--angle) * -2) at 85% 10%, var(--accent3), transparent 20% 80%, var(--accent3));
          box-shadow: inset var(--base) 0 0 var(--shadow) calc(var(--shadow) * 0.2);
          filter: blur(var(--blur)) contrast(var(--contrast));
          animation: spin var(--spin-duration) linear infinite;
        }
        .color-orb::after {
          background-image: radial-gradient(circle at center, var(--base) var(--dot), transparent var(--dot));
          background-size: calc(var(--dot) * 2) calc(var(--dot) * 2);
          backdrop-filter: blur(calc(var(--blur) * 2)) contrast(calc(var(--contrast) * 2));
          mix-blend-mode: overlay;
          mask-image: radial-gradient(black var(--mask), transparent 75%);
        }
        @keyframes spin {
          to { --angle: 360deg; }
        }
        @media (prefers-reduced-motion: reduce) {
          .color-orb::before { animation: none; }
        }
      `}</style>
    </div>
  );
}
