---
name: Ouroboros
description: A self-verifying production-intelligence agent for film & TV
colors:
  bg-near-black: "#15120f"
  ink-warm-white: "#ede7dd"
  surface-card: "#1f1b17"
  surface-popover: "#262019"
  ember-orange: "#fb631b"
  ember-orange-foreground: "#15120f"
  surface-hover: "#2c261e"
  alert-red: "#e5484d"
  hairline: "#332c24"
  ink-dim: "#9c9186"
typography:
  display:
    fontFamily: "Fraunces, ui-serif, Georgia, serif"
    fontWeight: 500
    letterSpacing: "normal"
  body:
    fontFamily: "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif"
    fontWeight: 400
    fontSize: "0.875rem"
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, SFMono-Regular, monospace"
    fontWeight: 400
rounded:
  sm: "0.3rem"
  md: "0.4rem"
  lg: "0.5rem"
  xl: "0.7rem"
components:
  button-primary:
    backgroundColor: "{colors.ember-orange}"
    textColor: "{colors.ember-orange-foreground}"
    rounded: "{rounded.lg}"
    padding: "0 10px"
  button-secondary:
    backgroundColor: "{colors.surface-popover}"
    textColor: "{colors.ink-warm-white}"
    rounded: "{rounded.lg}"
  button-outline:
    backgroundColor: "{colors.bg-near-black}"
    textColor: "{colors.ink-warm-white}"
    rounded: "{rounded.lg}"
  badge-outline:
    backgroundColor: "{colors.bg-near-black}"
    textColor: "{colors.ink-warm-white}"
    rounded: "9999px"
  card:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.lg}"
---

# Design System: Ouroboros

## Overview

**Creative North Star: "The Screening Room at Night"**

A dark theater, not a dark app. The near-black ground (`#15120f`) is a deliberate, warm, film-stock choice — never pure black, never a generic dashboard's `#000` or `#111`. Against it burns exactly one warm light: the brand ember-orange, used like a projector's glow through the dark, rare enough that it always reads as a signal, never as decoration. Everything else — text, hairlines, cards — sits in a narrow band of warm charcoal and bone, so the orange has nowhere to hide.

The product's real subject (a system that keeps re-checking a film's claims against the live world, faster as release nears) shows up structurally, not just in copy: a single true-scale instrument (the Reality Drift ring) leads every project page, and a ranked, hairline-divided worklist replaces the generic tile grid a status dashboard reaches for by default. The system reads like an instrument panel married to a legal clearance ledger — precise, quiet, occasionally urgent — not like a SaaS admin panel with a film skin over it.

No confirmed visual rejections beyond the above: light mode, a second accent color, and rounded "friendly" illustration were never on the table for this product.

**Key Characteristics:**
- Warm near-black ground, never pure black
- One accent color, used rarely and only with intent
- Editorial serif display paired with a workhorse sans body
- Monospace reserved for anything that is genuinely a measurement
- Flat surfaces, hairline dividers instead of shadows or nested cards
- A ranked list over a tile grid, wherever both are options

## Colors

The palette is Restrained: neutrals plus one accent, never scattered — the accent is rationed, not decorative.

### Primary
- **Ember Orange** (`#fb631b`): the brand's one accent. Used for the Reality Drift ring's fill, the primary button, active nav state, and the focus ring — never for large background fields or illustration. If it appears twice in the same glance, that's a lot.

### Neutral
- **Near-Black** (`#15120f`): the page ground everywhere. Warm, not blue-black — a film/celluloid bias, a chosen neutral rather than a default dark-mode gray.
- **Warm Bone** (`#ede7dd`): primary text and icon color on the near-black ground.
- **Card Charcoal** (`#1f1b17`): the one raised surface — cards, the top-level chrome (drift hero, sticky action bar). One step lighter than the ground, never a second, brighter "elevated" tier above it.
- **Popover Charcoal** (`#262019`): the next surface up — popovers, the sidebar's account footer hover, the drift ring's own track color.
- **Hover Charcoal** (`#2c261e`): shadcn's own "accent" role — a subtle hover/highlight surface. Distinct from the brand accent above; never confuse the two.
- **Hairline** (`#332c24`): every border and divider in the system. Borders are always this one value; nothing is invented per-component.
- **Dim Ink** (`#9c9186`): secondary/muted text — labels, captions, timestamps, anything that should read as quieter than the primary text without dropping below body-text contrast.

### Alert
- **Signal Red** (`#e5484d`): reserved for `blocking`/`high` risk indicators and destructive actions. Never used for anything else — its rarity is what makes a red dot mean something the instant you see it.

### Named Rules
**The One Light Rule.** The brand ember-orange is the only saturated color in the system. Every other value is a neutral warm gray or near-black. A second accent color is never introduced for a new feature — route it through gray or through the existing red/orange pair instead.

## Typography

**Display Font:** Fraunces (with ui-serif, Georgia, serif fallback)
**Body Font:** IBM Plex Sans (with ui-sans-serif, system-ui, sans-serif fallback)
**Label/Mono Font:** IBM Plex Mono (with ui-monospace, SFMono-Regular, monospace fallback)

**Character:** An editorial serif with real personality (Fraunces' soft, slightly quirky terminals) paired against a plain, workhorse grotesque body — the pairing of a film magazine's masthead with its actual reporting, not two display faces competing for attention.

### Hierarchy
- **Display** (500 weight, Fraunces, `text-2xl`–`text-3xl`): page and project titles only (`Demo Film`, `Ouroboros` in the sidebar). Never for body copy or labels.
- **Body** (400 weight, IBM Plex Sans, `text-sm`): all prose, claim text, descriptions, button labels.
- **Label/Data** (400–500 weight, IBM Plex Mono): reserved for anything that is a measurement, an identifier, or a timestamp — the Reality Drift ring's percentage, the 7-day/spend/days-to-release instrument row, the cadence badge (`1h`/`1d`/`1w`), claim/project IDs. Never used as a "technical-looking" costume on prose that isn't actually data.

### Named Rules
**The Measurement-Only Mono Rule.** IBM Plex Mono appears only where the value is a genuine measurement, identifier, or timecode. A label describing something ("Needs attention", "Reality Drift") is always the body sans, in title case — never mono, never tracked-caps.

## Layout

Single-column content per page, capped implicitly by the app shell (a fixed-width left nav + a fluid content column), not a centered max-width container — this is an operate-mode tool, not a marketing page. Density is generous at the hero (large instrument, real breathing room) and tightens in the worklist (hairline-divided rows, compact vertical rhythm) — the page's own density shift mirrors "look, then act."

Responsive behavior: the left nav collapses to a hamburger-triggered overlay drawer below `md` (768px); the hero's instrument row and ring both scale down fluidly rather than breaking to a different composition. A persistent action bar sticks to the bottom of the scrollable content area on every viewport, with enough bottom padding on the content above it that the last scrollable item never sits behind it.

## Elevation & Depth

Flat by design — no shadows anywhere in the system. Depth is conveyed entirely through tonal layering: near-black ground → card charcoal → popover charcoal, each one step lighter, plus hairline borders where a tonal step alone isn't enough to read as a boundary (e.g. the sticky action bar's top edge).

### Named Rules
**The Flat-By-Default Rule.** Surfaces separate by color step and hairline, never by shadow. A drop shadow appearing anywhere in this system is a defect, not a variant.

## Shapes

Corners are gently rounded throughout (`0.5rem` base radius, `--radius`), scaled down slightly for small controls (badges are fully pill-rounded) and up slightly for larger surfaces. No sharp corners, no heavy rounding — the radius reads as "considered," not as a personality statement in either direction. Borders are always the single hairline value (`#332c24`, 1px); nothing is drawn with a heavier or colored border.

## Components

### Buttons
- **Shape:** `0.5rem` radius, never pill-shaped except icon-only variants.
- **Primary:** ember-orange fill, near-black (`#15120f`) text — reserved for the single most important action on a view (Run CLEAR). Amended 2026-09-06: white text on this orange sits at 3.04:1, under WCAG AA's 4.5:1 floor (found live via Lighthouse); near-black text on the same orange is 6.13:1 — same brand color, a readable label.
- **Secondary:** popover-charcoal fill, warm-bone text — a real but lower-emphasis action (Run TRUE CUT).
- **Outline / Ghost:** near-black or transparent fill with a hairline border or hover-charcoal hover state — the default for anything that isn't the page's primary action (Trigger monitors, Sign out, Cancel).
- **Hover / Focus:** buttons darken or lighten by roughly 20% opacity shift on hover; focus-visible gets a 3px ember-orange ring, never a browser-default blue outline.

### Badges
- **Style:** pill-shaped (`9999px`), outline variant by default (hairline border, warm-bone text) for the cadence badge and risk labels; never filled unless the badge itself needs primary emphasis.

### Cards
- **Corner Style:** `0.5rem`.
- **Background:** card-charcoal, one step above the page ground.
- **Shadow Strategy:** none — see Elevation & Depth.
- **Border:** none by default; a hairline top border only where a card sits directly below another surface with no gap (e.g. the sticky action bar).
- **Internal Padding:** generous — headers and content both use at least `1rem`, more at the hero.

### Inputs
- **Style:** `0.5rem` radius, hairline border, transparent/near-black background.
- **Focus:** border shifts to the ember-orange ring color plus a 3px ring, matching buttons.

### Navigation (Left Nav)
- **Style:** fixed-width (`16rem`) column, popover-charcoal-adjacent sidebar tone, IBM Plex Sans labels. Active route gets a hover-charcoal fill and medium weight, never the brand accent (the accent stays rationed for the one primary action per view). Below `md`, becomes a full-height overlay drawer triggered by a hamburger button in a slim mobile header strip.

### The Reality Drift Ring (signature component)
A hand-drawn SVG arc, not a charting-library gauge — echoes the ouroboros mark's own nearly-closed circular stroke. Thick stroke (`26px` on a `220px` viewBox), hairline track underneath in the border color, ember-orange fill arc, IBM Plex Mono percentage at the center. Renders at hero scale (`14rem` diameter) as the page's one true-scale instrument, never shrunk into a small topbar widget.

### The Coil Spiral (signature component, marketing site)
Added 2026-09-06 for the public marketing site's landing/how-it-works pages. A single continuous SVG path (an Archimedean spiral, ember-orange stroke, always sampled at the same point count regardless of how many turns it draws) that visibly winds tighter to dramatize the product's real re-verification cadence — never a decorative loading spinner. Loose (~1 turn) at the hero; tightens as the visitor scrolls through the loop's stages; static at a fixed mid-tight setting (~2.5 turns) on the How It Works page. The same fixed-point-count technique is what lets the `d` attribute animate smoothly in CSS between turn counts.

## Do's and Don'ts

### Do:
- **Do** reserve ember-orange for exactly one primary signal per view — the ring's fill, one primary button, active nav, or a focus ring. Never two unrelated uses of it in the same glance.
- **Do** use IBM Plex Mono only for genuine measurements, IDs, and timecodes (**The Measurement-Only Mono Rule**).
- **Do** convey depth through tonal steps and hairlines, never shadows (**The Flat-By-Default Rule**).
- **Do** prefer a ranked, hairline-divided list over a tile grid when the content has a natural priority order (risk, urgency, time).

### Don't:
- **Don't** introduce a second saturated accent color for a new feature — route through the existing neutral/red/orange set instead.
- **Don't** add a kicker or eyebrow label above a heading, anywhere in this system — a banned pattern regardless of brief, per the project's own craft floor.
- **Don't** add drop shadows, glass/blur decoration, or colored side-borders on cards or list rows.
- **Don't** shrink the Reality Drift ring (or any future signature instrument) into a decorative small widget — it renders at true scale or not at all.
