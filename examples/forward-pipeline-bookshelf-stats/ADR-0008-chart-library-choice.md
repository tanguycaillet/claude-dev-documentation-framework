---
id: ADR-0008
title: "Chart.js for stats visualization"
status: accepted
date: 2026-04-10
triggered_by: PLAN-0002
implementation_tasks:
  - "Chart.js integration"
  - "Reading stats dashboard component"
supersedes: null
superseded_by: null
---

## Context

REQ-0003 requires a bar chart of pages read per month. The project uses React. We need to choose a charting library. This is Decision D2 from PLAN-0002.

Constraints:
- Mobile-first: bundle size matters. The app targets 375px viewports on 4G.
- The chart is a simple bar chart — one dataset, 12 bars, a Y-axis, month labels on X. No real-time streaming, no zooming, no custom SVG overlays.
- Must be maintainable by a developer who doesn't specialize in data visualization.

## Decision

Use **Chart.js** via the `react-chartjs-2` wrapper, importing only the bar chart module.

```ts
import { Bar } from 'react-chartjs-2';
import { Chart, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
Chart.register(BarElement, CategoryScale, LinearScale, Tooltip);
```

This import strategy keeps the addition to the bundle at ~34kB gzipped.

## Consequences

**Positive:**
- Simple, declarative API — the component is ~60 lines including data transformation
- Tree-shakeable: importing only the bar chart and required scales keeps bundle impact low
- Excellent documentation; wide community; low risk of abandonment
- Accessible out of the box (ARIA labels on canvas elements)

**Negative:**
- Less compositional than D3 — if we ever need a genuinely custom visualization (e.g., a reading heatmap), we'll need a different library for that chart. Acceptable since the scope of REQ-0003 is one bar chart.
- `react-chartjs-2` is a thin wrapper and occasionally lags Chart.js major versions by a few weeks

## Alternatives Considered

- **Recharts:** React-native API, fully composable JSX. Bundle cost (~45kB gzipped for a bar chart) is higher than Chart.js with tree-shaking. API is more verbose for a simple use case. Would be preferred if we needed deeply custom React interactivity (e.g., tooltip driven by React state shared with other components). Deferred — if we add a second chart type with shared state, reconsider.
- **D3:** Maximum flexibility, minimum abstraction. Bundle can be kept small with selective imports (~20kB). However, D3's imperative, DOM-mutation model is awkward inside React's declarative render cycle. Requires significant wrapper code for a simple bar chart. Rejected — the complexity cost is not justified by the requirements.
- **Nivo:** Beautiful defaults, good React integration. Bundle size is large (~120kB for a bar chart module). Rejected on mobile bundle grounds.
- **Tremor / shadcn charts:** Opinionated UI components built on Recharts. Ties us to their design system. Rejected — we have our own design tokens and don't want the coupling.

## Implementation

- `npm install chart.js react-chartjs-2` (pinned to Chart.js ^4.x)
- New component: `src/components/StatsDashboard/MonthlyBarChart.tsx`
- Props: `data: { month: string; pages: number }[]`, `year: number`
- Register only: `BarElement`, `CategoryScale`, `LinearScale`, `Tooltip` — nothing else
- Snapshot test + one accessibility test (alt text on canvas)
