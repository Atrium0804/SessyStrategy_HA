# Brand & Theme Tokens

*Last updated: 2026-08-01 | Part of [Reference Documentation](../index.md)*

Source: **NS Huisstijl Richtlijnen v4.4** (corporate brand guide). This page translates the
print-oriented corporate identity into web tokens for the MkDocs **Material** theme so the
documentation stays on-brand while keeping the focus on content.

---

## Color palette

All values are taken directly from the corporate guide. Do not alter these hex values.

### Primary base colors

| Role | Name | Hex | RGB |
|------|------|-----|-----|
| Brand accent | Yellow (Geel) | `#FFC917` | 255, 201, 23 |
| Brand primary | Dark blue (Donkerblauw) | `#003082` | 0, 48, 130 |
| Surface | White (Wit) | `#FFFFFF` | 255, 255, 255 |
| Interactive | Light blue (Lichtblauw) | `#0079D3` | 0, 121, 211 |
| Interactive (a11y web) | Light blue — accessibility variant | `#0063D3` | 0, 99, 211 |

> The guide permits `#0063D3` **only for websites** where the standard light blue fails
> contrast requirements. Use it for links and interactive elements on light backgrounds.

### Accent colors (functional — draw attention to important information only)

| Semantic use | Name | Hex |
|--------------|------|-----|
| Success / tip | Green (Groen) | `#00C690` |
| Danger / error | Red (Rood) | `#FF0045` |
| Warning | Orange (Oranje) | `#FF8200` |
| Example / custom | Purple (Paars) | `#D500F0` |
| Note / muted | Gray (Grijs) | `#6D6E70` |

> Accent colors are never used in the logo, headings, or body text — only to flag important
> information (for example, admonition accents). Magenta `#FF006D` and the light-blue "flow"
> are reserved for **NS International** and are not used here.

### Neutrals

| Role | Name | Hex |
|------|------|-----|
| Body text (softer than black) | Dark gray | `#383E42` |

---

## Typography

| Role | Corporate font | Weights | Web fallback stack |
|------|----------------|---------|--------------------|
| Headings & body | NS Sans | Regular, Bold | `"NS Sans", "Segoe UI", system-ui, Arial, sans-serif` |
| Monospace (code) | not defined by NS | — | `"JetBrains Mono", "SFMono-Regular", Consolas, monospace` |

Notes from the guide (and our deployment reality):

- **NS Sans** is the house typeface and is installed on corporate laptops, so the docs use it
  directly with no web-font download. Off-corporate devices fall back to Segoe UI / system UI.
- **Frutiger** is the guide's secondary face for extra weights, but it is **not available on
  corporate laptops**, so we do not use it. NS Sans (regular + bold) covers our needs.
- Headings: NS Sans **bold**, tight letter-spacing (~ -30% in print terms → roughly
  `-0.01em` on the web), start with a capital, line-height 90–110%.
- Do not substitute a serif or decorative font.

---

## Theme mapping (Material)

The corporate identity is print-first: yellow is dominant on posters. For a **content-focused
documentation site**, yellow is used as a restrained accent (yellow text fails contrast on
white), dark blue carries the primary role, and light blue drives interaction.

### Light scheme (`default`)

| Material token | Value | From |
|----------------|-------|------|
| `--md-primary-fg-color` | `#003082` | Dark blue |
| `--md-accent-fg-color` | `#0063D3` | Light blue (a11y variant) |
| `--md-default-bg-color` | `#FFFFFF` | White |
| `--md-typeset-color` (body text) | `#383E42` | Dark gray |
| Brand highlight (logo area, active TOC) | `#FFC917` | Yellow — non-text use only |

### Dark scheme (`slate`)

| Material token | Value | Rationale |
|----------------|-------|-----------|
| `--md-primary-fg-color` | `#0a2a63` | Deep NS blue header — calm on dark |
| `--md-accent-fg-color` | `#4d8ee0` | Lightened light blue for contrast on dark |
| `--md-default-bg-color` | `#12161c` | Near-black blue-gray derived from `#383E42` |
| `--md-typeset-color` | `#e6e8eb` | Off-white body text |

Yellow `#FFC917` is not used as a text or header background color. In both schemes it appears
only as a thin brand rule under the header (`.md-header` border), preserving the NS
yellow-and-blue identity without competing with the content.

### Admonition accents

Map Material admonition types to the functional accent colors:

| Admonition | Color |
|------------|-------|
| `tip` / `success` | Green `#00C690` |
| `danger` / `error` | Red `#FF0045` |
| `warning` | Orange `#FF8200` |
| `example` | Purple `#D500F0` |
| `note` | Gray `#6D6E70` |

---

## Accessibility guardrails

- Yellow `#FFC917` **must not** be used for text on white — it fails WCAG AA. Use it only for
  non-text brand elements (logo backdrop, active markers, decorative rules).
- On light backgrounds, prefer `#0063D3` over `#0079D3` for links (the guide's own
  accessibility exception).
- Target WCAG AA (4.5:1) for all body text in both light and dark schemes.
