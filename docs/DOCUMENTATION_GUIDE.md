# Documentation Guide

*Draft — last updated: 2026-08-01*

This is the single source of truth for **how we write and style the SessyStrategy HA
documentation**. It is written for two audiences at once: human contributors and AI agents.
Follow it for every new page or edit so the docs stay coherent now and in the future.

> Companion pages:
> [Brand & Theme Tokens](reference/brand-tokens.md) (colors, fonts, theme mapping) ·
> [Style Guide](STYLE_GUIDE.md) (quick formatting reference) ·
> [Agent Rules](AGENT_RULES.md) (detailed agent formatting rules).

---

## 1. Goals

1. **Content first.** The theme and styling exist to keep attention on the words, not on
   decoration. When in doubt, remove.
2. **Coherent.** Every page looks and reads like it came from the same author.
3. **On-brand.** Visual identity follows the NS corporate guide (see
   [Brand & Theme Tokens](reference/brand-tokens.md)).
4. **Durable.** A new contributor or agent can produce a correct page from this guide alone.

---

## 2. Structure — Diátaxis

Every page belongs to exactly one of four categories. This is already reflected in the folder
layout under `docs/`. Pick the right one before writing.

| Category | Folder | Answers | Voice |
|----------|--------|---------|-------|
| Tutorial | `docs/tutorials/` | "Teach me, step by step." | Guiding, encouraging |
| How-to guide | `docs/how-to/` | "Help me do a specific task." | Direct, task-focused |
| Explanation | `docs/explanation/` | "Help me understand why." | Reflective, background |
| Reference | `docs/reference/` | "Give me the facts." | Neutral, precise |

Do not mix categories on one page. If a how-to grows a long "why", move the "why" into an
explanation page and link to it.

---

## 3. Page template

Start every page with this shape:

```markdown
# Page Title

*Last updated: YYYY-MM-DD | Part of [<Section>](../)*

Short intro sentence stating what the page is for.

---

## First real section
```

Rules:

- One `#` H1 per page, matching the nav title.
- Sentence-style capitalization in headings ("Configure seasonal mode", not "Configure
  Seasonal Mode").
- Keep the `Last updated` line current whenever you meaningfully change a page.

---

## 4. Voice & tone

Grounded in the NS identity: **personal, warm, professional, dynamic** — applied to technical
writing:

- Write in the **second person** ("you set", "you deploy").
- Prefer **short, active sentences**. One idea per sentence.
- Be **concrete**: name the entity, the file, the value.
- No marketing language, no hype, no filler ("simply", "just", "obviously").
- Define an acronym once, then reuse it.

For prose conventions beyond this guide, defer to the **Google Developer Documentation Style
Guide** (capitalization, lists, numbers, UI element formatting).

---

## 5. Formatting rules

These keep the "minimal distraction" look. Allowed and prohibited elements are listed in full
in [Style Guide](STYLE_GUIDE.md); the essentials:

**Use:**

- Headings, tables, ordered/unordered lists, code fences with a language tag.
- **Admonitions** (Material syntax) for emphasis:

  ```markdown
  !!! note
      Additional context.

  !!! warning
      Something that can go wrong.

  !!! tip
      A helpful shortcut.
  ```

- **Mermaid** for all diagrams, always with the neutral theme:

  ```markdown
  ```mermaid
  %%{init: {'theme': 'neutral'}}%%
  flowchart TD
      A[Start] --> B{Decision}
  ```
  ```

- Backticks for `entities`, `files`, and `code`.

**Avoid:**

- Decorative emoji (only `❌` / `⚠️` for faults are allowed).
- Raster images — use Mermaid instead.
- Colored inline text, custom Unicode icons, strikethrough, decorative rules.
- Deep heading nesting (stop at H3 where possible).

---

## 6. Color & type

Do not hardcode colors in page content. Color lives in the theme, defined once from the
[Brand & Theme Tokens](reference/brand-tokens.md):

- **Dark blue** primary, **light blue** for links, **yellow** as a restrained non-text accent.
- Admonition colors map to the NS functional accent colors (green = tip, red = danger,
  orange = warning, purple = example, gray = note).
- Body text uses the neutral dark gray, not pure black.
- Never place text in NS yellow on a white background (fails contrast).

---

## 7. Links & cross-references

- Link the **first** mention of another concept to its explanation or reference page.
- Use relative links within `docs/` (for example `[Architecture](reference/architecture.md)`).
- Reference entities and config keys with backticks and, where a canonical page exists, link
  them (for example [`apps.yaml`](reference/configuration/)).

---

## 8. Before you commit — checklist

- [ ] Page is in the correct Diátaxis folder and category.
- [ ] Single H1, sentence-case headings, `Last updated` line present.
- [ ] Second-person, active voice; no hype words.
- [ ] Admonitions and Mermaid use the approved syntax/theme.
- [ ] No raster images, decorative emoji, or hardcoded colors.
- [ ] First mention of each concept links to its canonical page.
- [ ] `mkdocs serve` renders the page with no build warnings.

---

## 9. For AI agents specifically

- Read this guide and [Agent Rules](AGENT_RULES.md) before generating documentation.
- Match the structure and tone of an existing page in the same category rather than inventing
  a new layout.
- Never introduce new colors, fonts, or components — reuse the theme tokens.
- When behavior or configuration changes in the code, update the matching reference/how-to
  page in the same change, and bump its `Last updated` date.
- If a requested page does not fit one Diátaxis category, ask which category is intended
  instead of blending several.
