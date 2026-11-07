/**
 * App-wide settings. Change the product name, navigation or upload limits here
 * rather than inside components.
 */
export const siteConfig = {
  name: "Multisource",
  tagline: "Ask your documents and data, get answers you can verify.",
  repoUrl: "https://github.com/ionicbond12203/multisource-ai-agent",

  /**
   * Top navigation. Set `available: false` for pages that are not built yet;
   * they render as a non-clickable "Soon" item instead of a broken link.
   */
  nav: [
    { label: "Workspace", href: "/", available: true },
    { label: "Agents", href: "/agents", available: false },
    { label: "Evaluations", href: "/evaluations", available: false },
    { label: "How it works", href: "/how-it-works", available: false },
  ],

  upload: {
    maxFileSizeBytes: 20 * 1024 * 1024,
    acceptedExtensions: [".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"],
  },
} as const;

export type NavItem = (typeof siteConfig.nav)[number];
