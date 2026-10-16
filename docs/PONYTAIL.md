# Ponytail evidence

Official source: https://github.com/DietrichGebert/ponytail

The user approved installation on 2026-10-16. These official commands both completed successfully:

```text
codex plugin marketplace add DietrichGebert/ponytail
codex plugin add ponytail@ponytail
```

Installed path: `C:/Users/vishw/.codex/plugins/cache/ponytail/ponytail/5.2.0`.
The installed plugin manifest and `skills/ponytail/SKILL.md` were inspected. The implementation applies
its full-mode principles: read the affected flow, minimize dependencies, preserve validation/security,
write tests for risky behavior and report unchecked scope.

`hooks/claude-codex-hooks.json` declares SessionStart, SubagentStart and UserPromptSubmit. The current
manifest contains three hook events although the README describes trusting two lifecycle hooks.
Codex configuration now contains three Ponytail hook trust hashes. This agent did not write them.
Their presence and plugin enablement do not prove that a hook executed in this chat.
No hook execution or activation is claimed without /hooks or runtime-event evidence.
Open `/hooks` yourself, review the installed definitions, trust the intended hooks and start a new chat
to activate them through Codex's supported trust flow.

The official `skills/ponytail-audit/SKILL.md` was also read and applied as a manual one-shot audit.
The installed `skills/ponytail-review/SKILL.md` was also applied after changes.
See reports/PONYTAIL_AUDIT.md and reports/PONYTAIL_REVIEW.md. This is skill-guided review, not proof that a slash command or lifecycle
hook ran. No subagent was created; the implementation remains one modular backend.

Ponytail is separate from Ruff/Pylint, strict type checking, Pytest, Git pre-commit and CI.
