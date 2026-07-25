# Troubleshooting

## Playwright Cannot Find Chromium

Install Chromium in the same environment used to run the renderer:

```bash
python -m playwright install chromium
```

If the project pins `PLAYWRIGHT_BROWSERS_PATH`, use the same value for install and render.

The renderer intentionally does not fall back to system Chrome. This prevents
headless rendering failures from opening or crashing the user's regular browser.
Keep the original Chromium launch error visible and fix that environment instead.

## Source Article Not Found

Use an absolute `source`, or set `project_root` in the manifest/config when the article path is repo-relative.

## Image Block Not Found

Markdown image paths are resolved from the article directory, `project_root`, and the current working directory. For site-root paths like `/images/foo.jpg`, set `project_root` so the renderer can check `project_root/static/images/foo.jpg`. Prefer article-relative image paths for portable examples.

## Text Overflows

Run with `--qa`. If QA reports overflow, reduce the font size in `styles/article.css` or simplify unusually long unbroken text. The browser paginator handles normal Chinese paragraphs and quotes without manual page breaks.
