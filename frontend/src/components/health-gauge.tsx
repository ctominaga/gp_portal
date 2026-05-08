"use client";

import { cn } from "@/lib/utils";
import type { HealthBand } from "@/lib/types";

export interface HealthGaugeProps {
  score: number; // 0..100
  band: HealthBand;
  size?: "sm" | "md" | "lg";
  className?: string;
  /** Mostra label explicativo abaixo do número. */
  showLabel?: boolean;
}

const BAND_COLOR: Record<HealthBand, { stroke: string; fill: string; text: string }> = {
  green: { stroke: "#16a34a", fill: "#dcfce7", text: "text-green-700" },
  amber: { stroke: "#d97706", fill: "#fef3c7", text: "text-amber-700" },
  red: { stroke: "#dc2626", fill: "#fee2e2", text: "text-red-700" },
};

const SIZES = {
  sm: { box: 80, stroke: 8, font: 18, sub: 10 },
  md: { box: 140, stroke: 12, font: 36, sub: 12 },
  lg: { box: 200, stroke: 16, font: 52, sub: 14 },
};

const BAND_LABEL: Record<HealthBand, string> = {
  green: "Saudável",
  amber: "Atenção",
  red: "Crítico",
};

/**
 * Gauge SVG visualmente óbvio do Health Score.
 * Arco de 270° (de -135° a +135°), preenchido proporcional ao score,
 * com cor da banda. Número grande no centro.
 */
export function HealthGauge({
  score,
  band,
  size = "md",
  className,
  showLabel = true,
}: HealthGaugeProps) {
  const dims = SIZES[size];
  const c = dims.box / 2;
  const r = c - dims.stroke;
  const colors = BAND_COLOR[band];

  // Arco de -135° a +135° (varredura de 270°)
  const startAngle = -225; // SVG: 0° = direita; -225° = topo-esquerda
  const endAngle = 45;
  const angleSpan = endAngle - startAngle; // 270
  const fraction = Math.max(0, Math.min(1, score / 100));
  const filledEnd = startAngle + angleSpan * fraction;

  const polar = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return { x: c + r * Math.cos(rad), y: c + r * Math.sin(rad) };
  };
  const arcPath = (a1: number, a2: number) => {
    const p1 = polar(a1);
    const p2 = polar(a2);
    const large = a2 - a1 > 180 ? 1 : 0;
    return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${large} 1 ${p2.x} ${p2.y}`;
  };

  return (
    <div className={cn("flex flex-col items-center gap-1", className)}>
      <svg width={dims.box} height={dims.box} viewBox={`0 0 ${dims.box} ${dims.box}`}>
        {/* fundo do arco */}
        <path
          d={arcPath(startAngle, endAngle)}
          stroke="#e5e7eb"
          strokeWidth={dims.stroke}
          fill="none"
          strokeLinecap="round"
        />
        {/* preenchido */}
        {fraction > 0 && (
          <path
            d={arcPath(startAngle, filledEnd)}
            stroke={colors.stroke}
            strokeWidth={dims.stroke}
            fill="none"
            strokeLinecap="round"
          />
        )}
        <text
          x="50%"
          y="50%"
          dominantBaseline="middle"
          textAnchor="middle"
          fontSize={dims.font}
          fontWeight={700}
          className={colors.text}
          fill="currentColor"
        >
          {Math.round(score)}
        </text>
        <text
          x="50%"
          y="50%"
          dy={dims.font * 0.85}
          dominantBaseline="middle"
          textAnchor="middle"
          fontSize={dims.sub}
          className="fill-muted-foreground"
        >
          / 100
        </text>
      </svg>
      {showLabel && (
        <span className={cn("text-xs font-medium", colors.text)}>
          {BAND_LABEL[band]}
        </span>
      )}
    </div>
  );
}
