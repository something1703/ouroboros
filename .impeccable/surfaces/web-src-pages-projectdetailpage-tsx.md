---
version: 1
slug: "web-src-pages-projectdetailpage-tsx"
primary_target: "web/src/pages/ProjectDetailPage.tsx"
related_targets: []
---

## Direction contract

THESIS: Reality Drift is the page, not a topbar afterthought — one true-scale instrument leads, and everything beneath it is a ranked worklist, not a wall of status tiles.

OWN-WORLD: existing dark-editorial palette/type exactly as committed (`#15120F` bg, `#FB631B` brand, Fraunces/IBM Plex Sans/IBM Plex Mono) — shadcn Card/Badge/Button vocabulary, no new tokens; claim rows carry a live cascade transition on status change (borrowed grammar, not new color).

STORY: a legal/editorial/producer user opens a project, instantly reads how much risk drifted, then sees exactly which claims need a human decision first — ranked, not buried in aggregate counts.

FIRST VIEWPORT: one oversized Reality Drift ring (SVG arc, no chart library) centered top; `drift_7d` / spend / days-to-release / cadence badge as a compact instrument row beneath it; then a "Needs attention" worklist — claims sorted by risk level — replacing the old status/risk tile grid; role-gated quick actions as a persistent bottom bar.

FORM: dealt structure "Reality Drift, Hero-Scaled" (index 6 of 7 grounded candidates), fused with the split-flap-concourse challenger's ranked/live-cascade row grammar. Seed key d79ab0ed.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
