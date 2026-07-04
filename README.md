# markdown-to-image

[English](README.md) | [简体中文](README.zh-CN.md)

Installable Agent Skill for turning Markdown articles into ordered PNG slide images for social publishing, especially RedNote/Xiaohongshu-style article cards.

This repository follows the Agent Skills folder layout: the reusable instructions live in `skills/markdown-to-image/SKILL.md`, and the deterministic renderer lives beside it under `scripts/`. It works best in tools that can load Agent Skills, and the renderer can also be run manually from the command line.

## Install

Install from GitHub with the `skills` CLI:

```bash
npx skills add https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image
```

Install globally for a specific agent:

```bash
# Cursor
npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a cursor -y

# Codex
npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a codex -y

# Claude Code
npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a claude-code -y
```

Check that the skill is discoverable:

```bash
npx skills add https://github.com/wygmjdd/markdown-to-image --list
```

Common skill-aware targets include Cursor, Codex, Claude Code, OpenCode, GitHub Copilot, and other agents supported by the `skills` CLI. If your tool does not load Agent Skills natively, clone this repository and ask the agent to read `skills/markdown-to-image/SKILL.md`, then run the renderer script from the manual CLI section below.

If you are using a Codex model inside Cursor, install the skill for Cursor. The host app decides where skills are discovered; the model name does not change the install target. See the [`skills` CLI README](https://github.com/vercel-labs/skills) for the current list of supported agents.

## Recommended Usage With An Agent

In normal use, ask your agent to use `markdown-to-image` and tell it the article path plus output directory.

Example prompt:

```text
使用 markdown-to-image 这个 skill，把下面这篇文章生成 RedNote / 小红书图片：
/path/to/wygmjdd.github.io/content/docs/2026/06/example.md

输出目录放到：
/path/to/wygmjdd.github.io/static/red-images/articles/example/

请生成 manifest.json、图片和 post-caption.md。
```

The agent should read the article, propose title candidates, wait for your title choice, write `manifest.json` in the output directory, render the images, run QA, and summarize the output files.

## Stable Defaults

Use a config file for stable account and category defaults. This is more reliable than repeating the same instructions to the agent every time.

Copy `markdown-to-image.config.example.yml` to `markdown-to-image.config.yml` in your article project:

```yaml
# Optional, when output manifests live outside the article project:
# project_root: /absolute/path/to/source/repo
nickname: 我要改名叫嘟嘟
bio: 一个用文字分享生活和读书感悟的程序员
chars_per_slide: 340
default_cta: reading

cta_mapping:
  reading:
    - yue-du-shu-mu
    - du-shu
  summary:
    - zong-jie
  life:
    - 30-fen-zhong-ri-ji
    - qin-mi-guan-xi
```

The renderer looks for config in this order:

1. the manifest directory
2. parent directories of the manifest directory
3. `project_root` from the manifest
4. the current working directory

After a config file is found, `project_root` from that config can still be used to resolve repo-relative `source` paths and site-root images.

Use config for values that should stay stable across articles:

| Config field | Controls |
| --- | --- |
| `project_root` | Base directory for repo-relative `source` paths and site-root images. |
| `nickname` | Body slide footer and end-slide handle. |
| `bio` | End-slide author bio. |
| `chars_per_slide` | Default body text limit per body slide. |
| `default_cta` | Fallback CTA theme when no category mapping matches. |
| `cta_mapping` | Maps article `primary_category` slugs to `reading`, `summary`, or `life`. |

The built-in CTA labels are `reading` → `读书感悟`, `summary` → `总结复盘`, and `life` → `生活分享`.

Use the per-article `manifest.json` for values that change per article: `social_title`, `cta_line1`, optional `cover_base`, and article-specific overrides. If the manifest sets `project_root`, `nickname`, `bio`, `cta_theme`, or `cta_label`, the manifest wins over the config. Use `cta_label` when you want an exact custom label instead of the built-in labels.

## Output Rule

The renderer writes PNGs beside the manifest.

If the manifest is here:

```text
/path/to/output-dir/manifest.json
```

the images are written here:

```text
/path/to/output-dir/01-cover.png
/path/to/output-dir/02.png
/path/to/output-dir/03.png
...
/path/to/output-dir/NN-end.png
```

So yes: when using a skill-aware agent, usually you can just tell the model the desired output directory.

## Complete Example

This repository includes a complete moved example from a `wygmjdd.github.io` article:

```text
skills/markdown-to-image/examples/wygmjdd-article/
```

It contains the input article, the manifest, the generated image results, and the publishing caption:

```text
article.md
images/001.jpg
images/002.jpg
manifest.json
01-cover.png
02.png
03.png
04.png
05.png
06.png
07.png
08-end.png
post-caption.md
```

The example manifest is self-contained, so it does not need a local blog checkout path:

```json
{
  "manifest_version": 1,
  "source": "article.md",
  "original_title": "15岁带弟弟上坡挖洋芋，20年后再来一次",
  "social_title": "上坡挖洋芋时，母亲连说五个谜语，我突然一点不累了",
  "primary_category": "30-fen-zhong-ri-ji",
  "cta_theme": "life",
  "cta_line1": "那时节，我忽然觉得已经很是疲倦的身体，似乎一点累也感受不到了。",
  "nickname": "我要改名叫嘟嘟",
  "bio": "一个用文字分享生活和读书感悟的程序员",
  "chars_per_slide": 340
}
```

For a Hugo/static site, a practical output location is:

```text
static/red-images/articles/<article-slug>/
```

When the manifest lives inside that output directory and the source article stays in another repository, use either an absolute `source` path or set `project_root` in the manifest or config with a repo-relative `source`.

## Manual CLI Usage

Manual rendering is useful for testing or rerendering an existing manifest. From this repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r skills/markdown-to-image/scripts/requirements.txt
.venv/bin/python -m playwright install chromium
```

Render the lightweight bundled sample:

```bash
.venv/bin/python skills/markdown-to-image/scripts/render_markdown_to_image.py \
  --manifest skills/markdown-to-image/examples/manifest.json \
  --qa
```

Rerender the complete copied example in a temporary directory:

```bash
tmpdir="$(mktemp -d)"
cp -R skills/markdown-to-image/examples/wygmjdd-article/. "$tmpdir/"
.venv/bin/python skills/markdown-to-image/scripts/render_markdown_to_image.py \
  --manifest "$tmpdir/manifest.json" \
  --qa
```

Render a blog output directory:

```bash
.venv/bin/python skills/markdown-to-image/scripts/render_markdown_to_image.py \
  --manifest /path/to/wygmjdd.github.io/static/red-images/articles/<slug>/manifest.json \
  --qa
```

## Generated Files

Typical output:

```text
manifest.json
01-cover.png
02.png
03.png
...
NN-end.png
post-caption.md
```

`post-caption.md` is typically written by the agent as a publishing helper. The renderer itself writes the PNG files.

## Manifest Fields

Required:

| Field | Meaning |
| --- | --- |
| `manifest_version` | Use `1`. |
| `source` | Markdown article path. Absolute or relative. |
| `original_title` | Original article title. |
| `social_title` | Title rendered on cover and body headers. |
| `cta_line1` | End-slide closing sentence. |

Common optional fields:

| Field | Meaning |
| --- | --- |
| `project_root` | Base directory for repo-relative `source` paths. |
| `primary_category` | Source article category. |
| `cta_theme` | `reading`, `summary`, `life`, or custom label key. |
| `cta_label` | Exact cover/end label override. |
| `nickname` | Author handle. |
| `bio` | Short end-slide bio. |
| `chars_per_slide` | Maximum body text characters per body slide before browser fit checks. Default: `340`. |
| `cover_base` | Optional background image beside `manifest.json`, usually `cover-base.png`. |

More detail: `skills/markdown-to-image/references/manifest.md`.

## Cover Backgrounds

By default the renderer creates a text-first paper cover with no background image.

Use `cover_base` only when the article has a strong visual scene and a quiet background helps recognition:

```json
{
  "cover_base": "cover-base.png"
}
```

Put `cover-base.png` beside `manifest.json` and set `cover_base` in the manifest. A leftover `cover-base.png` is ignored when the manifest does not declare a cover background, so removing the field disables the background. Do not ask image models to draw Chinese title text; the renderer overlays real text.

## Git Ignore Advice

Generated social images usually should not be committed.

For a Hugo/static site, a good pattern is:

```gitignore
static/red-images/*
!static/red-images/.gitkeep
```

This keeps the output directory in git while ignoring generated PNGs and manifests.

## Troubleshooting

### Playwright Cannot Find Chromium

Run:

```bash
python -m playwright install chromium
```

Use the same Python environment for install and render.

### Source Article Not Found

Use an absolute `source`, or set `project_root` in the manifest or config:

```json
{
  "project_root": "/absolute/path/to/source/repo",
  "source": "content/docs/path/to/article.md"
}
```

### Image Paths Do Not Resolve

Prefer relative paths beside the article for portable examples. For site-root paths like `/images/foo.jpg`, the renderer checks `project_root/static/images/foo.jpg` first when `project_root` is set, then falls back to `static/images/foo.jpg` under the current working directory.

### QA Shows Underfill Warnings

Underfill warnings mean a body slide has visible empty space. They are review prompts, not always failures. Inspect the PNGs and rerender only if the page looks awkward.

### QA Shows Overflow Errors

Overflow errors are blockers. Shorten unusual unbroken text, adjust the article, or tune the CSS in `skills/markdown-to-image/scripts/markdown_to_image/styles/article.css`.

## License

MIT
