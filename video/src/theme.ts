/** Brand design tokens — mirrors frontend/tailwind.config.ts */
export const colors = {
  dark: "#2C3E50",
  mid: "#4A6FA5",
  light: "#C5D8F0",
  beige: "#F5F0EB",
  stone: "#D4C9B8",
  muted: "#8A7F74",
  success: "#5A8A5A",
  warning: "#C8A951",
  danger: "#C0392B",
  white: "#FFFFFF",
} as const;

export const fonts = {
  body: "Inter, system-ui, -apple-system, sans-serif",
} as const;

/** Standard 1080p at 30fps */
export const VIDEO = {
  width: 1920,
  height: 1080,
  fps: 30,
  /** Duration per scene in seconds */
  sceneDuration: 5,
} as const;
