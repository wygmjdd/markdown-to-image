---
name: markdown-to-image
description: Generate social-media slide images from Markdown articles. Use when an AI agent needs to convert a Markdown post into ordered PNG cards, including RedNote-style article slides and X four-image long-form posts.
---

# Markdown To Image

Turn a Markdown article into an ordered PNG slide series for social publishing.

The bundled renderer is in `scripts/`. It parses frontmatter Markdown, strips inline links to anchor text, preserves inline code plus fenced/indented code blocks as readable code cards, paginates body text with Chromium-measured fit, renders platform-specific slide sets, and can run QA for overflow.

## Setup

Use a project venv or the user's active Python environment:

```bash
python -m pip install -r <skill-dir>/scripts/requirements.txt
python -m playwright install chromium
```

If the user has a project-local browser cache policy, follow it. For example:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/playwright-browsers" \
  .venv/bin/python -m playwright install chromium
```

## Workflow

1. Confirm the target platform first: `rednote` or `x`.
2. Read the Markdown article and frontmatter.
3. Check for stable defaults in `markdown-to-image.config.yml` or `.markdown-to-image.yml` in the output/manifest directory, its parent directories, manifest `project_root`, or the current working directory.
4. Propose 3 social title candidates and wait for the user's explicit choice. For X, the chosen title is rendered inside `01.png`.
5. Write `manifest.json` beside the desired output images. Put stable identity fields in config when possible; use the manifest for per-article overrides.
   - RedNote: include `platform: "rednote"`, `cta_line1`, and optional cover settings.
   - X: include `platform: "x"`; omit `cta_line1` unless the user wants it for caption text.
   - X mode renders only article text by default; embedded article images do not consume the 4 image slots unless `x_include_images: true` is set.
6. Run the renderer:

```bash
python <skill-dir>/scripts/render_markdown_to_image.py --manifest <output-dir>/manifest.json --qa
```

7. Create a short post caption file if the user is preparing a social upload.
8. Tell the user the output folder and that images should be uploaded in filename order.

## Manifest

Read `references/manifest.md` when writing or editing a manifest.

Minimum manifest:

```json
{
  "manifest_version": 1,
  "platform": "rednote",
  "source": "path/to/article.md",
  "original_title": "Original article title",
  "social_title": "Chosen social title",
  "cta_line1": "One article-specific closing line."
}
```

Minimum X manifest:

```json
{
  "manifest_version": 1,
  "platform": "x",
  "source": "path/to/article.md",
  "original_title": "Original article title",
  "social_title": "Chosen social title"
}
```

Use `project_root` when `source` is repo-relative but the manifest lives outside that repo. `project_root` may live in the manifest or stable config. Relative `source` paths are resolved against `project_root`, the manifest directory, then the current working directory.

Stable defaults can live in `markdown-to-image.config.yml`:

```yaml
# Optional, when output manifests live outside the article project:
# project_root: /absolute/path/to/source/repo
platform: rednote
nickname: Author handle
bio: Short bio
chars_per_slide: 340
default_cta: reading
cta_mapping:
  reading:
    - yue-du-shu-mu
  life:
    - 30-fen-zhong-ri-ji
```

The config controls defaults only. Manifest fields such as `platform`, `nickname`, `bio`, `cta_theme`, and `cta_label` override config values for a single article.

## Platform Behavior

- `rednote` (default): writes `01-cover.png`, body slides, and `NN-end.png`.
- `x`: writes up to 4 body images named `01.png` through `04.png`; no cover or end slide. The renderer increases slide height as needed so long articles fit into the 4-image limit. The chosen `social_title` is rendered at the top of `01.png`.

Set `x_include_images: true` when X output should composite Markdown/HTML article images into the body flow. Inline images are rendered inside the same `01.png`-`04.png` files, with surrounding text continuing before and after the image; they are not emitted as separate upload images.

## Cover Background

Default RedNote output uses the text-only paper cover. Add `cover_base: "cover-base.png"` only when the article has a strong visual scene and the user wants an image-backed cover. The image file must live beside `manifest.json`; leftover cover images are ignored unless the manifest declares a cover background. X mode does not render a cover.

Do not ask an image model to draw title text; the renderer overlays the real title.

## QA

Run with `--qa` after rendering. Treat QA errors as blockers. Warnings about sparse pages are review prompts; inspect the generated PNGs before deciding whether to adjust content or accept them.
