# Manifest Reference

The renderer reads a JSON manifest and writes PNG files into the manifest directory.

Missing or blank required fields fail fast before rendering.

## Required Fields

```json
{
  "manifest_version": 1,
  "source": "examples/sample.md",
  "original_title": "Original title",
  "social_title": "Social title",
  "cta_line1": "Closing line"
}
```

## Common Optional Fields

- `project_root`: Base directory for repo-relative `source` paths.
- `social_title`: Title rendered on cover and body slide headers.
- `primary_category`: Article category from the source project.
- `cta_theme`: `reading`, `summary`, `life`, or a custom label key.
- `cta_label`: Exact label override shown on cover and end slides.
- `nickname`: Author handle shown on body slide footer and end slide.
- `bio`: Short bio shown on end slide.
- `chars_per_slide`: Maximum body text characters per body slide before browser fit checks. Default: `340`.
- `cover_base`: Optional background image beside the manifest, normally `cover-base.png`.

## Stable Config

Use `markdown-to-image.config.yml` or `.markdown-to-image.yml` for defaults shared by many articles. The renderer searches the manifest directory, parent directories, manifest `project_root`, then the current working directory. After config is found, config `project_root` can still resolve repo-relative `source` paths and site-root images.

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
  life:
    - 30-fen-zhong-ri-ji
```

Config defaults are applied before rendering. Manifest fields override config values for a single article. If neither `cta_theme` nor `cta_label` is set in the manifest, `primary_category` is matched through `cta_mapping`; unmatched categories use `default_cta`.

## Source Resolution

Relative `source` paths are resolved in this order:

1. `project_root/source`, when `project_root` is set in the manifest or config
2. `manifest_directory/source`
3. `current_working_directory/source`

Use absolute paths when running from an automation that may change directories.

## Output Files

The renderer writes:

- `01-cover.png`
- `02.png`, `03.png`, ...
- `NN-end.png`

Upload files in filename order.

## Cover Background

Set `cover_base`, `cover_ai`, or `cover_bg` in the manifest to enable a cover background image. A leftover `cover-base.png` is ignored when the manifest does not declare a cover background.
