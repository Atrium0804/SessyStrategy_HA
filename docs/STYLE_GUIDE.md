# Documentation Style Guide

**SessyStrategy HA | Stephen Few Minimal Distraction Principle**

> *For complete AI agent guidelines, see [AGENT_RULES.md](AGENT_RULES.md)*

---

## Quick Reference

This is a condensed reference for human contributors. For AI agent-specific rules, see [AGENT_RULES.md](AGENT_RULES.md).

### Allowed Formatting

| Element | Syntax | Example |
|---------|--------|---------|
| Headers | `#`, `##`, `###` | `# Configuration` |
| Mermaid diagrams | ```mermaid | See below |
| Admonitions | `!!! note`, `!!! warning`, `!!! tip` | `!!! note` |
| Checklists | `- [x]`, `- [ ]` | `- [x] Complete` |
| Fault indicators | `❌`, `⚠️` | `❌ Error:` |
| Code blocks | ```yaml | ```yaml\nkey: value\n``` |
| Bold | `**text**` | `**Save**` |
| Italic | `_text_` | `_Note:_` |
| Code | `` `text` `` | `` `apps.yaml` `` |
| Tables | Markdown | Standard format |

### Prohibited

- ❌ Emoji (except ❌ and ⚠️ for faults/warnings)
- ❌ Colored text
- ❌ Images (use Mermaid instead)
- ❌ Custom Unicode icons
- ❌ Green checkmarks (use `[x]`)
- ❌ Decorative formatting

---

## Mermaid Theme

**Always use neutral theme:**

```mermaid
%%{init: {'theme': 'neutral'}}%%
```

---

## Rendering (MkDocs Material)

The published site is built with `mkdocs` + the Material theme (see `mkdocs.yml`). Admonitions
require the `!!! type` block syntax from the `admonition` extension — the older `[!note]`-style
call-out does not render and shows up as literal text.

### Admonition Types Used

| Type | Syntax | Rendered As |
|------|--------|-------------|
| Note | `!!! note` | Styled box with note icon |
| Warning | `!!! warning` | Styled box with warning icon |
| Tip | `!!! tip` | Styled box with tip icon |
| Caution | `!!! caution` | Styled box (generic icon) |

Content under the marker must be indented by four spaces:

```markdown
!!! note
    This is a note. Content is indented four spaces under the marker line.
```

---

## Document Structure (All Types)

```
---
title: Document Title
description: Purpose
author: Name
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
---

# Document Title

Introduction paragraph.

!!! note
    Optional admonition for important context.

## Section

Content.

### Subsection

More content.

```mermaid
%%{init: {'theme': 'neutral'}}%%
```

## Troubleshooting

- ❌ Error: Description
- ⚠️ Warning: Description

## Quick Checklist

- [x] Task 1
- [ ] Task 2
```

---

## By Document Type

### Tutorials
- Start with "What You Will Learn"
- Include prerequisites as checklist
- Step-by-step format
- End with verification and next steps

### How-to Guides
- Start with Problem/Solution
- Include related documentation
- Solution steps section
- Common issues with fixes

### Explanations
- Start with Concept Overview
- Include key terms table
- Use Mermaid for visual representation
- Include practical implications

### Reference
- Start with Overview (Purpose, Scope, Audience)
- Technical details in tables
- Include examples
- Usage notes with best practices

---

## See Also

- [AGENT_RULES.md](AGENT_RULES.md) - Detailed AI agent guidelines
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [DOCUMENTATION_PLAN.md](../DOCUMENTATION_PLAN.md) - Documentation roadmap

---

*Last updated: 2026-08-14*

