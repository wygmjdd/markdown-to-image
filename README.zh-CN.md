# markdown-to-image

[English](README.md) | 简体中文

一个可安装的 Agent Skill，用来把 Markdown 文章渲染成一组适合社交平台发布的 PNG 图片，尤其适合 RedNote / 小红书风格的文章卡片。

这个仓库采用 Agent Skills 的目录结构：可复用的使用说明放在 `skills/markdown-to-image/SKILL.md`，稳定的图片生成脚本放在 `skills/markdown-to-image/scripts/`。支持 Agent Skills 的工具可以直接安装使用；不支持的工具也可以手动运行渲染脚本。

## 安装

使用 `skills` CLI 从 GitHub 安装：

```bash
npx skills add https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image
```

安装到指定 Agent：

```bash
# Cursor
npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a cursor -y

# Codex
npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a codex -y

# Claude Code
npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a claude-code -y
```

查看仓库里有哪些可安装的 skill：

```bash
npx skills add https://github.com/wygmjdd/markdown-to-image --list
```

常见的 skill-aware 工具包括 Cursor、Codex、Claude Code、OpenCode、GitHub Copilot，以及 `skills` CLI 支持的其他 Agent。如果你是在 Cursor 里使用 Codex 模型，安装目标应该选 `cursor`；决定 skill 放到哪里的，是宿主工具，不是模型名。可参考 [`skills` CLI README](https://github.com/vercel-labs/skills) 查看当前支持的 Agent。

如果你的工具暂时不能原生加载 Agent Skills，也可以 clone 这个仓库，让 Agent 阅读 `skills/markdown-to-image/SKILL.md`，再按下方「手动运行」的方式执行渲染脚本。

## 推荐用法

日常使用时，直接告诉 Agent：使用 `markdown-to-image`，并给它文章路径和输出目录。

示例提示词：

```text
使用 markdown-to-image 这个 skill，把下面这篇文章生成 RedNote / 小红书图片：
/path/to/wygmjdd.github.io/content/docs/2026/06/example.md

输出目录放到：
/path/to/wygmjdd.github.io/static/red-images/articles/example/

请生成 manifest.json、图片和 post-caption.md。
```

Agent 应该先阅读文章，给出几个社交平台标题候选；等你确认标题后，在输出目录写入 `manifest.json`，运行渲染脚本生成图片，执行 QA 检查，最后告诉你生成了哪些文件。

## 稳定配置

像作者昵称、作者简介、分类小标题、默认分页字数这类跨文章稳定的东西，建议写进配置文件，不要每次都只靠口头告诉 Agent。

把仓库里的 `markdown-to-image.config.example.yml` 复制到你的文章项目里，并命名为 `markdown-to-image.config.yml`：

```yaml
# 可选：当 manifest 位于输出目录、文章在另一个项目里时使用。
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

渲染器会按下面顺序查找配置文件：

1. `manifest.json` 所在目录
2. `manifest.json` 所在目录的父目录
3. manifest 里的 `project_root`
4. 当前工作目录

找到配置文件之后，配置文件里的 `project_root` 仍然会用来解析仓库相对 `source` 和站点根路径图片。

适合放进配置文件的稳定项：

| 配置字段 | 控制内容 |
| --- | --- |
| `project_root` | 用来解析仓库相对 `source` 和站点根路径图片的根目录。 |
| `nickname` | 正文页页脚账号名，以及结束页账号名。 |
| `bio` | 结束页作者简介。 |
| `chars_per_slide` | 每张正文页默认最大字数。 |
| `default_cta` | 没有命中分类映射时使用的默认 CTA 主题。 |
| `cta_mapping` | 把文章 frontmatter 里的 `primary_category` 分类映射到 `reading`、`summary` 或 `life`。 |

内置 CTA 标签是：`reading` → `读书感悟`，`summary` → `总结复盘`，`life` → `生活分享`。

单篇文章变化的内容仍然放在 `manifest.json` 里，比如 `social_title`、`cta_line1`、可选的 `cover_base`。如果 manifest 里写了 `project_root`、`nickname`、`bio`、`cta_theme` 或 `cta_label`，会覆盖配置文件。想精确指定分类小标题时，用 `cta_label`。

## 输出规则

渲染器会把 PNG 图片写在 `manifest.json` 所在目录。

如果 manifest 在这里：

```text
/path/to/output-dir/manifest.json
```

图片会生成在这里：

```text
/path/to/output-dir/01-cover.png
/path/to/output-dir/02.png
/path/to/output-dir/03.png
...
/path/to/output-dir/NN-end.png
```

所以，使用 Agent 时通常只需要告诉它目标输出目录即可。

## 完整示例

仓库里带了一个从 `wygmjdd.github.io` 迁移过来的完整示例：

```text
skills/markdown-to-image/examples/wygmjdd-article/
```

这个示例包含原文、原始配图、manifest、已经生成好的图片结果，以及可复制发布用的 caption：

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

示例 manifest 是自包含的，不依赖你本地的博客仓库路径：

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

对于 Hugo/static 站点，推荐把输出放到类似下面的位置：

```text
static/red-images/articles/<article-slug>/
```

当 manifest 位于输出目录，而原始文章还在另一个仓库里时，可以使用绝对 `source` 路径；也可以在 manifest 或配置文件里设置 `project_root`，再使用相对 `source` 路径。

## 手动运行

手动运行适合测试、调试或重新渲染已有 manifest。在仓库根目录执行：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r skills/markdown-to-image/scripts/requirements.txt
.venv/bin/python -m playwright install chromium
```

渲染轻量示例：

```bash
.venv/bin/python skills/markdown-to-image/scripts/render_markdown_to_image.py \
  --manifest skills/markdown-to-image/examples/manifest.json \
  --qa
```

在临时目录重新渲染完整示例：

```bash
tmpdir="$(mktemp -d)"
cp -R skills/markdown-to-image/examples/wygmjdd-article/. "$tmpdir/"
.venv/bin/python skills/markdown-to-image/scripts/render_markdown_to_image.py \
  --manifest "$tmpdir/manifest.json" \
  --qa
```

渲染博客输出目录：

```bash
.venv/bin/python skills/markdown-to-image/scripts/render_markdown_to_image.py \
  --manifest /path/to/wygmjdd.github.io/static/red-images/articles/<slug>/manifest.json \
  --qa
```

## 生成文件

一次典型输出包含：

```text
manifest.json
01-cover.png
02.png
03.png
...
NN-end.png
post-caption.md
```

`post-caption.md` 通常由 Agent 作为发布辅助文件写入；渲染器本身只负责生成 PNG 图片。

## Manifest 字段

必填字段：

| 字段 | 含义 |
| --- | --- |
| `manifest_version` | 使用 `1`。 |
| `source` | Markdown 文章路径，可以是绝对路径或相对路径。 |
| `original_title` | 原文章标题。 |
| `social_title` | 渲染在封面和正文页顶部的社交平台标题。 |
| `cta_line1` | 结束页上的收束句。 |

常用可选字段：

| 字段 | 含义 |
| --- | --- |
| `project_root` | 用来解析仓库相对 `source` 的根目录。 |
| `primary_category` | 原文章分类。 |
| `cta_theme` | `reading`、`summary`、`life`，或自定义标签 key。 |
| `cta_label` | 封面和结束页显示的精确标签，会覆盖 `cta_theme`。 |
| `nickname` | 作者昵称。 |
| `bio` | 结束页上的短简介。 |
| `chars_per_slide` | 每张正文页的最大正文字数，之后还会经过浏览器实际适配检查。默认 `340`。 |
| `cover_base` | 可选封面背景图，通常为 `cover-base.png`，放在 `manifest.json` 同目录。 |

更详细的 manifest 说明见 `skills/markdown-to-image/references/manifest.md`。

## 封面背景

默认情况下，渲染器会生成无背景图的纸感文字封面。

只有当文章有明确视觉场景、且你希望封面更有辨识度时，才建议使用 `cover_base`：

```json
{
  "cover_base": "cover-base.png"
}
```

把 `cover-base.png` 放在 `manifest.json` 同目录，并在 manifest 里设置 `cover_base`。如果 manifest 没有声明封面背景，残留的 `cover-base.png` 会被忽略；删除字段就能禁用背景。不要让图片模型直接生成中文标题文字；标题文字应该由渲染器叠加，清晰度和可控性会好很多。

## Git Ignore 建议

生成的社交图片通常不建议提交到博客仓库。

如果是 Hugo/static 站点，可以这样忽略：

```gitignore
static/red-images/*
!static/red-images/.gitkeep
```

这样目录会保留在 git 中，但生成出来的 PNG 和 manifest 不会被提交。

## 常见问题

### Playwright 找不到 Chromium

运行：

```bash
python -m playwright install chromium
```

注意：安装 Chromium 和运行渲染脚本要使用同一个 Python 环境。

### 找不到源文章

使用绝对 `source` 路径，或者在 manifest / 配置文件里设置 `project_root`：

```json
{
  "project_root": "/absolute/path/to/source/repo",
  "source": "content/docs/path/to/article.md"
}
```

### 图片路径解析失败

为了让示例更容易迁移，优先使用文章旁边的相对图片路径。对于 `/images/foo.jpg` 这种站点根路径，如果设置了 `project_root`，渲染器会先查找 `project_root/static/images/foo.jpg`，再回退到当前工作目录下的 `static/images/foo.jpg`。

### QA 出现 underfill warning

`underfill` 表示正文页下方空白较多，是检查提示，不一定是错误。看一下生成图，如果页面观感可以，就可以接受。

### QA 出现 overflow error

`overflow` 是阻断问题。可以缩短异常长的连续文本，调整文章内容，或修改 `skills/markdown-to-image/scripts/markdown_to_image/styles/article.css` 里的样式。

## License

MIT
