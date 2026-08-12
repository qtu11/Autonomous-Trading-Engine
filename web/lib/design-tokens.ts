/**
 * design-tokens.ts - Single source of truth for design system.
 * Import this instead of duplicating palette in every component.
 */
export const C = {
  // Background
  bgMain: '#020305',
  bgPanel: 'rgba(8, 12, 22, 0.92)',
  bgDark: '#010102',
  bgMuted: 'rgba(0, 0, 0, 0.3)',
  bgGlass: 'rgba(5, 7, 12, 0.95)',
  
  // Border
  border: 'rgba(255, 255, 255, 0.06)',
  borderHighlight: 'rgba(255, 255, 255, 0.1)',
  
  // Brand
  gold: '#D4B483',
  goldBright: '#F0D5A0',
  goldDim: 'rgba(212, 175, 55, 0.12)',
  
  // Semantic
  green: '#22d3a0',
  greenBright: '#10b981',
  greenDim: 'rgba(34, 211, 160, 0.15)',
  red: '#f43f5e',
  redBright: '#ef4444',
  redDim: 'rgba(244, 63, 94, 0.15)',
  blue: '#38bdf8',
  blueDim: 'rgba(56, 189, 248, 0.12)',
  cyan: '#06b6d4',
  cyanDim: 'rgba(6, 182, 212, 0.12)',
  amber: '#f59e0b',
  amberBright: '#fbbf24',
  amberDim: 'rgba(245, 158, 11, 0.15)',
  purple: '#a855f7',
  
  // Text - WCAG AA compliant against #020305
  text: '#f8fafc',     // 19.5:1 contrast
  dim: '#cbd5e1',      // 14.2:1 contrast
  muted: '#94a3b8',    // 7.4:1 contrast (was #64748b - 3.8:1, FAILED AA)
  
  // Typography
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
} as const;

export type ColorToken = keyof typeof C;
