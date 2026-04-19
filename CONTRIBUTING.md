# Contributing

Thanks for considering a contribution. This framework is a living document — if something in here doesn't match your real-world experience, I want to hear about it.

## Ways to contribute

- **Report friction.** If you tried to adopt this framework and hit a wall — the templates were unclear, a rule didn't survive contact with reality, an ID scheme clashed with something — open an issue using the "Friction report" template.
- **Suggest clarifications.** If a section of `docs/documentation-approach.md` confused you, open an issue. Confusion is a bug in documentation.
- **Propose extensions.** The framework intentionally stays small. If you think a new artifact type or cross-reference field is worth adding, propose it with a concrete use case that the current framework can't handle cleanly.
- **Add examples.** Worked examples are the most valuable teaching tool. If you use the framework on a real project and it worked well, contribute an anonymized worked example to the `examples/` directory.
- **Fix typos, broken links, formatting.** No issue needed — PR directly.

## Before you open a PR

1. **Check that it fits the philosophy.** This framework favors lightweight rituals over heavyweight process. Every artifact should be writable in under 10 minutes for a small feature. If your change makes the framework more bureaucratic, expect pushback.
2. **Keep the ID cross-references intact.** The traceability invariant (see README) is the core value proposition. Changes that weaken it are unlikely to be accepted.
3. **Match the existing tone.** Conversational but concrete. Short sentences. Examples over abstractions.
4. **One change per PR.** Easier to review, easier to revert.

## Style guide for documentation changes

- YAML frontmatter uses 2-space indentation, lowercase keys, and ISO-8601 dates (`2026-04-10`, not `04/10/26`)
- Artifact IDs are zero-padded to four digits: `REQ-0003`, `ADR-0012`
- Cross-references in prose use full IDs: write `ADR-0007`, not "the ADR" or "ADR 7"
- Code blocks are fenced with triple backticks and language hints
- Prefer Markdown tables over bullet lists for structured data

## Opening an issue

Use the issue templates when available. For free-form issues, include:
- What you were trying to do
- What the framework didn't help with
- What you tried as a workaround

## Opening a PR

- Reference the issue (if any): "Closes #12"
- Describe what changed and why
- If your change touches the framework spec (`docs/documentation-approach.md`), call that out — spec changes get more scrutiny than example or template changes

## Code of conduct

Be kind. Assume good faith. Disagree with ideas, not people. That's it.

## License

By contributing, you agree that your contributions will be licensed under the same [CC BY 4.0](LICENSE) license that covers the project.
