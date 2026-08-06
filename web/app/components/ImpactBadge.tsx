"use client";

interface ImpactBadgeProps {
  impact: string;
}

const styles: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  HIGH: { bg: "rgba(244,63,94,0.18)", text: "#f43f5e", border: "rgba(244,63,94,0.4)", glow: "0 0 10px rgba(244,63,94,0.3)" },
  MED: { bg: "rgba(245,158,11,0.18)", text: "#f59e0b", border: "rgba(245,158,11,0.4)", glow: "0 0 10px rgba(245,158,11,0.3)" },
  LOW: { bg: "rgba(100,116,139,0.15)", text: "#64748b", border: "rgba(100,116,139,0.3)", glow: "0 0 10px rgba(100,116,139,0.2)" },
};

export default function ImpactBadge({ impact }: ImpactBadgeProps) {
  const s = styles[impact.toUpperCase()] || styles.LOW;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 7px",
        fontSize: "6.5px",
        fontFamily: '"JetBrains Mono", monospace',
        fontWeight: 800,
        letterSpacing: "0.08em",
        color: s.text,
        background: s.bg,
        border: `1px solid ${s.border}`,
        borderRadius: "3px",
        boxShadow: s.glow,
        textTransform: "uppercase",
      }}
    >
      {impact.toUpperCase()}
    </span>
  );
}