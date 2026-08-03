# Repository Instructions

## Skill Source And Release Workflow

- Treat `skills/markdown-to-image/` in this repository as the only editable source of the skill.
- Never edit installed copies such as `~/.agents/skills/markdown-to-image/` or `~/.codex/skills/markdown-to-image/` directly.
- If an installed copy contains uncommitted drift, migrate and test that work in this repository before reinstalling; do not overwrite it silently.
- Run the repository test suite and the skill validator before publishing changes.
- Commit and push the source changes to `origin` before updating any installed copy.
- Update Codex only from the pushed remote:

```bash
npx skills add -g https://github.com/wygmjdd/markdown-to-image \
  --skill markdown-to-image -a codex -y
```

- After installation, compare the installed skill with `skills/markdown-to-image/` and run a representative render with `--qa`.
