import type { Persona } from "./types";

export const PERSONAS: Persona[] = [
  {
    id: 3,
    name: "Jamie Rivera",
    role: "employee",
    scope: "Own records",
    initials: "JR",
  },
  {
    id: 2,
    name: "Morgan Lee",
    role: "manager",
    scope: "Self + direct reports",
    initials: "ML",
  },
  {
    id: 1,
    name: "Avery Chen",
    role: "admin",
    scope: "All demo records",
    initials: "AC",
  },
];

export const DEMO_PROMPTS = [
  "How many hours did I log on Apollo this week?",
  "Show monthly hours by project as a chart.",
  "Can I approve my team's pending time entries?",
  "What is the weekly time submission deadline policy?",
  "帮我填报 2026-07-29 Apollo 项目 2 小时，备注：客户访谈",
];
