import type { VerdictKey } from "./api";

export const VERDICTS: Record<VerdictKey, { label: string; color: string; meaning: string }> = {
  reproduced: {
    label: "Reproduced",
    color: "var(--v-reproduced)",
    meaning: "The sandbox crashed exactly as claimed.",
  },
  needs_human: {
    label: "Needs human",
    color: "var(--v-needs-human)",
    meaning: "Claims check out, but the setup can't be reproduced automatically.",
  },
  not_reproduced: {
    label: "Not reproduced",
    color: "var(--v-not-reproduced)",
    meaning: "Steps ran three times with sanitizers on and nothing crashed.",
  },
  needs_info: {
    label: "Needs info",
    color: "var(--v-needs-info)",
    meaning: "No version, no steps, or no target named.",
  },
  duplicate: {
    label: "Duplicate",
    color: "var(--v-duplicate)",
    meaning: "Matches an earlier report.",
  },
  already_fixed: {
    label: "Already fixed",
    color: "var(--v-already-fixed)",
    meaning: "The cited code was changed in a later release.",
  },
  fabricated: {
    label: "Fabricated",
    color: "var(--v-fabricated)",
    meaning: "Cites code or a CVE that does not exist.",
  },
};

export const STAGES = [
  { key: "extract", label: "Extract claims" },
  { key: "ground", label: "Check the code" },
  { key: "outside", label: "Check CVEs and duplicates" },
  { key: "sandbox", label: "Reproduce in sandbox" },
  { key: "verdict", label: "Decide and explain" },
] as const;

export const CHANNELS: Record<string, string> = {
  github_issue: "GitHub issue",
  github_private_report: "Private vulnerability report",
  bouncer_form: "Bouncer form",
};

export function tierLabel(tier: string, provider: string): string {
  if (provider === "offline-rules") return "Rule-based fallback";
  return { nano: "Nemotron 3 Nano", super: "Nemotron 3 Super", ultra: "Nemotron 3 Ultra" }[tier] || tier;
}

export function sourceLabel(source?: string): string {
  if (!source) return "";
  const map: Record<string, string> = {
    "nemotron-nano": "Nemotron 3 Nano",
    "nemotron-super": "Nemotron 3 Super",
    "nemotron-ultra": "Nemotron 3 Ultra",
    rules: "Rule-based extractor (offline)",
    template: "Template text (offline, no model)",
    reporter: "Reporter's own commands",
  };
  return map[source] || source;
}
