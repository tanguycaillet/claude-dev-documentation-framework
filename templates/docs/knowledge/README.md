# Knowledge Base

Reference material, concepts, how-it-works articles, and bug/incident write-ups.

## Subdirectories

- `concepts/` — background and theory. "What is X?"
- `data-sources/` — one article per external data source we integrate with
- `models/` — explanations of algorithms, models, or complex logic in the codebase
- `scenarios/` — `SCN-NNNN` bug reports, incident write-ups, and debugging post-mortems

## Article format

Every knowledge article has YAML frontmatter:

```markdown
---
title: <Article title>
category: <concepts | data-sources | models | scenarios | other>
tags: [<tag1>, <tag2>]
audience: <developer | ops | all>
status: <draft | accepted | outdated>
last_updated: YYYY-MM-DD
---

# <Title>

<Content>
```

## When to write a knowledge article

- You learned something non-obvious and future-you (or a future teammate / AI session) will need to know it
- A bug, incident, or debugging session produced a generalizable lesson (→ `scenarios/`)
- An external system's quirks require documentation to work with it reliably (→ `data-sources/`)
- A model or algorithm in the code needs more explanation than fits in a docstring (→ `models/`)
