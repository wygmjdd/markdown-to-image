from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "markdown-to-image" / "scripts"


def _import_render_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from markdown_to_image import render

    return render


def _import_browser_paginator_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from markdown_to_image import browser_paginator

    return browser_paginator


def _import_paginator_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from markdown_to_image import paginator

    return paginator


def _import_parser_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from markdown_to_image import parser

    return parser


def _import_cli_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import render_markdown_to_image

    return render_markdown_to_image


def _import_qa_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from markdown_to_image import qa

    return qa


def test_render_article_slides_from_standalone_manifest(tmp_path: Path) -> None:
    render = _import_render_module()

    article_path = tmp_path / "article.md"
    article_path.write_text(
        "---\n"
        "title: 独立仓库测试\n"
        "primary_category: reading\n"
        "---\n"
        "第一段正文，有一个[链接](https://example.com)，渲染时只保留文字。\n\n"
        "> 引用内容。\n\n"
        "第二段正文。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "独立仓库测试",
                "social_title": "Markdown 可以独立生成图片",
                "cta_theme": "reading",
                "cta_line1": "把文章变成可以发布的图片组。",
                "nickname": "作者",
                "bio": "一个写作者",
                "chars_per_slide": 180,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, output_dir = render.render_article_slides(manifest_path)

    assert output_dir == tmp_path
    assert slides[0][0] == "01-cover.png"
    assert slides[-1][0].endswith("-end.png")
    assert "Markdown 可以独立生成图片" in slides[0][1]
    assert "链接" in slides[1][1]
    assert "](https://example.com)" not in slides[1][1]
    assert "引用内容" in slides[1][1]
    assert "把文章变成可以发布的图片组" in slides[-1][1]


def test_parser_preserves_fenced_and_indented_code_blocks() -> None:
    parser = _import_parser_module()

    blocks = parser.parse_body_blocks(
        "前文。\n\n"
        "```bash\n"
        "npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image\n"
        "```\n\n"
        "    # Codex\n"
        "    npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a codex -y\n\n"
        "后文。\n"
    )

    assert [block.kind for block in blocks] == ["paragraph", "code", "code", "paragraph"]
    assert blocks[1].code_language == "bash"
    assert blocks[1].text.startswith("npx skills add -g")
    assert "```" not in blocks[1].text
    assert blocks[2].text.splitlines()[0] == "# Codex"
    assert blocks[2].text.splitlines()[1].startswith("npx skills add -g")


def test_link_stripping_skips_code_blocks() -> None:
    parser = _import_parser_module()

    body = parser.strip_body_for_slides(
        "正文里有一个[普通链接](https://example.com)。\n\n"
        "```md\n"
        "[代码里的链接](https://example.com/keep)\n"
        "```\n\n"
        "    echo '[缩进代码链接](https://example.com/keep-too)'\n"
    )
    blocks = parser.parse_body_blocks(body)

    assert blocks[0].text == "正文里有一个普通链接。"
    assert blocks[1].text == "[代码里的链接](https://example.com/keep)"
    assert blocks[2].text == "echo '[缩进代码链接](https://example.com/keep-too)'"


def test_code_pagination_keeps_comment_headers_with_commands() -> None:
    paginator = _import_paginator_module()

    pieces = paginator.split_code_lines(
        "# Cursor\n"
        "npx skills add -g repo --skill markdown-to-image -a cursor -y\n"
        "# Codex\n"
        "npx skills add -g repo --skill markdown-to-image -a codex -y\n"
        "# Claude Code\n"
        "npx skills add -g repo --skill markdown-to-image -a claude-code -y",
        max_chars=42,
    )

    assert pieces == [
        "# Cursor\nnpx skills add -g repo --skill markdown-to-image -a cursor -y",
        "# Codex\nnpx skills add -g repo --skill markdown-to-image -a codex -y",
        "# Claude Code\nnpx skills add -g repo --skill markdown-to-image -a claude-code -y",
    ]


def test_code_pagination_splits_oversized_single_lines() -> None:
    paginator = _import_paginator_module()

    pieces = paginator.split_code_lines("token=" + "a" * 1800, max_chars=340)

    assert len(pieces) > 1
    assert all(len(piece) < 900 for piece in pieces)
    assert "".join(pieces) == "token=" + "a" * 1800


def test_code_pagination_preserves_spaces_in_long_commands() -> None:
    paginator = _import_paginator_module()
    command = "cat input.txt " + " | ".join(f"grep part{index}" for index in range(120))

    pieces = paginator.split_code_lines(command, max_chars=340)

    assert len(pieces) > 1
    assert "".join(pieces) == command


def test_code_blocks_render_as_dedicated_code_cards(tmp_path: Path) -> None:
    render = _import_render_module()

    article_path = tmp_path / "article.md"
    article_path.write_text(
        "安装方式如下：\n\n"
        "    # Cursor\n"
        "    npx skills add -g https://github.com/wygmjdd/markdown-to-image --skill markdown-to-image -a cursor -y\n\n"
        "> Cursor 使用符号`/`引出 Skill，Codex 使用符号`$`。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "代码块测试",
                "social_title": "代码块应该像代码",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert 'class="article-code-block"' in rendered
    assert '<pre class="article-code-pre"><code># Cursor' in rendered
    assert "npx skills add -g https://github.com/wygmjdd/markdown-to-image" in rendered
    assert '<code class="article-inline-code">/</code>' in rendered
    assert '<code class="article-inline-code">$</code>' in rendered


def test_long_single_line_code_block_renders(tmp_path: Path) -> None:
    render = _import_render_module()

    article_path = tmp_path / "article.md"
    long_line = "token=" + "a" * 1800
    article_path.write_text(
        "前文。\n\n"
        "```txt\n"
        f"{long_line}\n"
        "```\n\n"
        "后文。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "长代码测试",
                "social_title": "长代码也能渲染",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert "token=" in rendered
    assert "后文。" in rendered


def test_manifest_uses_social_title(tmp_path: Path) -> None:
    render = _import_render_module()

    article_path = tmp_path / "article.md"
    article_path.write_text("正文内容。\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "原始标题",
                "social_title": "公开字段标题",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)

    assert "公开字段标题" in slides[0][1]
    assert "公开字段标题" in slides[1][1]


def test_complete_example_renders_from_bundled_assets() -> None:
    render = _import_render_module()
    manifest_path = (
        ROOT
        / "skills"
        / "markdown-to-image"
        / "examples"
        / "wygmjdd-article"
        / "manifest.json"
    )

    slides, output_dir = render.render_article_slides(manifest_path)

    assert output_dir == manifest_path.parent
    assert slides[0][0] == "01-cover.png"
    assert slides[-1][0].endswith("-end.png")
    assert any("data:image/jpeg;base64," in html for _, html in slides)
    assert any("阿江、母亲" in html for _, html in slides)


def test_chars_per_slide_changes_body_pagination(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("这是一段没有标点的长文本" * 90, encoding="utf-8")

    def render_with_limit(limit: int) -> int:
        manifest_path = tmp_path / f"manifest-{limit}.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "manifest_version": 1,
                    "source": str(article_path),
                    "original_title": "分页测试",
                    "social_title": "分页测试标题",
                    "cta_line1": "结束语。",
                    "chars_per_slide": limit,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        slides, _ = render.render_article_slides(manifest_path)
        return len([name for name, _ in slides if name != "01-cover.png" and not name.endswith("-end.png")])

    assert render_with_limit(120) > render_with_limit(600)


def test_browser_paginated_pages_are_underfill_corrected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("第一段正文。\n\n第二段正文。\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "分页回填测试",
                "social_title": "分页回填测试标题",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    first_page = [render.ContentBlock("paragraph", "第一页内容。", 0)]
    second_page = [render.ContentBlock("paragraph", "被拉回第一页的内容。", 1)]
    corrected_pages = [[*first_page, *second_page]]
    called = False

    def fake_paginate_blocks_with_browser(*args, **kwargs):
        return [first_page, second_page]

    def fake_correct_body_page_underfills(pages, render_page_html):
        nonlocal called
        called = True
        assert pages == [first_page, second_page]
        return corrected_pages

    monkeypatch.setattr(render, "paginate_blocks_with_browser", fake_paginate_blocks_with_browser)
    monkeypatch.setattr(render, "correct_body_page_underfills", fake_correct_body_page_underfills)

    slides, _ = render.render_article_slides(manifest_path)
    body_slides = [name for name, _ in slides if name != "01-cover.png" and not name.endswith("-end.png")]

    assert called
    assert body_slides == ["02.png"]
    assert "被拉回第一页的内容" in slides[1][1]


def test_underfill_correction_is_followed_by_page_ending_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("第一段正文。\n\n第二段正文。\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "断句清理测试",
                "social_title": "断句清理测试标题",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    initial_pages = [[render.ContentBlock("paragraph", "原始第一页。", 0)]]
    dangling_pages = [
        [render.ContentBlock("paragraph", "第一页被回填到逗号，", 0)],
        [render.ContentBlock("paragraph", "后半句应该继续清理。", 0)],
    ]
    cleaned_pages = [[render.ContentBlock("paragraph", "第一页被回填到逗号，后半句应该继续清理。", 0)]]
    cleanup_called = False

    def fake_paginate_blocks_with_browser(*args, **kwargs):
        return initial_pages

    def fake_correct_body_page_underfills(pages, render_page_html):
        assert pages == initial_pages
        return dangling_pages

    def fake_cleanup_page_endings_with_browser(pages, render_page_html):
        nonlocal cleanup_called
        cleanup_called = True
        assert pages == dangling_pages
        return cleaned_pages

    monkeypatch.setattr(render, "paginate_blocks_with_browser", fake_paginate_blocks_with_browser)
    monkeypatch.setattr(render, "correct_body_page_underfills", fake_correct_body_page_underfills)
    monkeypatch.setattr(
        render,
        "cleanup_page_endings_with_browser",
        fake_cleanup_page_endings_with_browser,
    )

    slides, _ = render.render_article_slides(manifest_path)
    body_slides = [name for name, _ in slides if name != "01-cover.png" and not name.endswith("-end.png")]

    assert cleanup_called
    assert body_slides == ["02.png"]
    assert "第一页被回填到逗号，后半句应该继续清理。" in slides[1][1]


def test_cleanup_page_endings_with_browser_pulls_prefix_after_dangling_comma() -> None:
    render = _import_render_module()
    browser_paginator = _import_browser_paginator_module()
    pages = [
        [render.ContentBlock("paragraph", "第一页被回填到逗号，", 0)],
        [render.ContentBlock("paragraph", "后半句应该继续清理。", 0)],
    ]

    def render_probe(blocks: list, total: int, page_index: int = 0, all_pages: list | None = None) -> str:
        pages_snapshot = all_pages if all_pages is not None else [blocks]
        continues = False
        if page_index > 0 and pages_snapshot[page_index - 1] and blocks:
            previous_last = pages_snapshot[page_index - 1][-1]
            first_block = blocks[0]
            continues = (
                previous_last.kind == "paragraph"
                and first_block.kind == "paragraph"
                and previous_last.source_id == first_block.source_id
            )
        return render._render_body_page(
            "断句清理测试标题",
            blocks,
            1,
            max(total, 1),
            "作者",
            continues_paragraph=continues,
        )

    cleaned = browser_paginator.cleanup_page_endings_with_browser(pages, render_probe)

    assert len(cleaned) == 1
    assert "".join(block.text for block in cleaned[0]) == "第一页被回填到逗号，后半句应该继续清理。"


def test_missing_required_manifest_fields_fail_fast(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("正文内容。\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "原始标题",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="social_title.*cta_line1"):
        render.render_article_slides(manifest_path)


def test_site_root_article_images_resolve_from_project_root(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    image_dir = project_root / "static" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "photo.jpg").write_bytes(b"example image bytes")

    article_path = tmp_path / "article.md"
    article_path.write_text(
        '<figure><img src="/images/photo.jpg" alt="照片" /><figcaption>照片说明</figcaption></figure>',
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "project_root": str(project_root),
                "source": str(article_path),
                "original_title": "图片测试",
                "social_title": "图片测试标题",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)

    assert any("data:image/jpeg;base64," in html for _, html in slides)
    assert any("照片说明" in html for _, html in slides)


def test_project_config_supplies_stable_author_and_category_label(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    project_root.mkdir()
    (project_root / "markdown-to-image.config.yml").write_text(
        "nickname: 我要改名叫嘟嘟\n"
        "bio: 一个用文字分享生活和读书感悟的程序员\n"
        "chars_per_slide: 180\n"
        "default_cta: life\n"
        "cta_mapping:\n"
        "  reading:\n"
        "    - yue-du-shu-mu\n"
        "  life:\n"
        "    - 30-fen-zhong-ri-ji\n",
        encoding="utf-8",
    )
    article_path = project_root / "article.md"
    article_path.write_text(
        "---\n"
        "title: 配置测试\n"
        "primary_category: yue-du-shu-mu\n"
        "---\n"
        "第一段正文。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "output" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "project_root": str(project_root),
                "source": "article.md",
                "original_title": "配置测试",
                "social_title": "配置让作者信息稳定",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert "@我要改名叫嘟嘟" in rendered
    assert "一个用文字分享生活和读书感悟的程序员" in rendered
    assert "读书感悟" in rendered


def test_manifest_identity_fields_override_project_config(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    project_root.mkdir()
    (project_root / "markdown-to-image.config.yml").write_text(
        "nickname: 配置昵称\n"
        "bio: 配置简介\n"
        "default_cta: reading\n",
        encoding="utf-8",
    )
    article_path = project_root / "article.md"
    article_path.write_text("正文内容。\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "project_root": str(project_root),
                "source": "article.md",
                "original_title": "覆盖测试",
                "social_title": "单篇配置可以覆盖默认值",
                "cta_label": "自定义标签",
                "cta_line1": "结束语。",
                "nickname": "单篇昵称",
                "bio": "单篇简介",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert "@单篇昵称" in rendered
    assert "单篇简介" in rendered
    assert "自定义标签" in rendered
    assert "配置昵称" not in rendered


def test_prune_stale_slide_images_preserves_non_slide_png_assets(tmp_path: Path) -> None:
    cli = _import_cli_module()
    for name in (
        "01.png",
        "01-cover.png",
        "02.png",
        "03-end.png",
        "04.png",
        "10.png",
        "10-end.png",
        "001.png",
        "100.png",
        "cover-ai.png",
        "cover-bg.png",
        "diagram.png",
        "cover-base.png",
    ):
        (tmp_path / name).write_bytes(b"png")

    cli.prune_stale_slide_images(tmp_path, {"01-cover.png", "02.png", "03-end.png"})

    assert not (tmp_path / "01.png").exists()
    assert not (tmp_path / "04.png").exists()
    assert not (tmp_path / "10.png").exists()
    assert not (tmp_path / "10-end.png").exists()
    assert (tmp_path / "001.png").is_file()
    assert (tmp_path / "100.png").is_file()
    assert (tmp_path / "cover-ai.png").is_file()
    assert (tmp_path / "cover-bg.png").is_file()
    assert (tmp_path / "diagram.png").is_file()
    assert (tmp_path / "cover-base.png").is_file()


def test_existing_cover_base_is_ignored_without_manifest_cover_field(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("正文内容。\n", encoding="utf-8")
    (tmp_path / "cover-base.png").write_bytes(b"stale cover")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "封面背景测试",
                "social_title": "旧封面背景不会自动启用",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)

    assert '<div class="slide slide-cover">' in slides[0][1]


def test_declared_cover_base_marks_cover_as_image_backed(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("正文内容。\n", encoding="utf-8")
    (tmp_path / "background.png").write_bytes(b"png")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "封面背景测试",
                "social_title": "声明的背景图应启用轻蒙版",
                "cta_line1": "结束语。",
                "cover_base": "background.png",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)

    assert (
        '<div class="slide slide-cover has-background-image" style="background-image:'
        in slides[0][1]
    )


def test_cover_render_qa_rejects_low_contrast_title(monkeypatch, tmp_path: Path) -> None:
    qa = _import_qa_module()
    low_contrast_cover = """
    <!doctype html>
    <html>
      <head>
        <style>
          html, body { margin: 0; }
          .slide {
            position: relative;
            width: 1080px;
            height: 1440px;
            overflow: hidden;
            background: #fff;
          }
          .cover-title-card { position: absolute; inset: 120px; }
          .cover-kicker { color: #222; font: 32px sans-serif; }
          .cover-title { color: #fff; font: 96px/1.2 sans-serif; }
        </style>
      </head>
      <body>
        <div class="slide slide-cover">
          <div class="cover-title-card">
            <div class="cover-kicker">生活分享</div>
            <div class="cover-title">看不见的标题</div>
          </div>
        </div>
      </body>
    </html>
    """
    monkeypatch.setattr(
        qa,
        "render_article_slides",
        lambda _manifest_path: ([("01-cover.png", low_contrast_cover)], {}),
    )

    issues = qa._render_issues(tmp_path / "manifest.json")

    assert any(issue.code == "cover_low_contrast" for issue in issues)


def test_cover_render_qa_accepts_short_dark_title_on_light_background(
    monkeypatch,
    tmp_path: Path,
) -> None:
    qa = _import_qa_module()
    short_title_cover = """
    <!doctype html>
    <html>
      <head>
        <style>
          html, body { margin: 0; }
          .slide {
            position: relative;
            width: 1080px;
            height: 1440px;
            overflow: hidden;
            background: #fff;
          }
          .cover-title-card { position: absolute; inset: 120px; }
          .cover-kicker { color: #222; font: 32px sans-serif; }
          .cover-title {
            display: inline-block;
            color: #222;
            font: 96px/1.2 sans-serif;
          }
        </style>
      </head>
      <body>
        <div class="slide slide-cover">
          <div class="cover-title-card">
            <div class="cover-kicker">生活分享</div>
            <div class="cover-title">一</div>
          </div>
        </div>
      </body>
    </html>
    """
    monkeypatch.setattr(
        qa,
        "render_article_slides",
        lambda _manifest_path: ([("01-cover.png", short_title_cover)], {}),
    )

    issues = qa._render_issues(tmp_path / "manifest.json")

    assert not any(issue.code == "cover_low_contrast" for issue in issues)


def test_cover_render_qa_checks_text_background_not_region_extremes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    qa = _import_qa_module()
    locally_low_contrast_cover = """
    <!doctype html>
    <html>
      <head>
        <style>
          html, body { margin: 0; }
          .slide {
            position: relative;
            width: 1080px;
            height: 1440px;
            overflow: hidden;
            background: #fff;
          }
          .cover-title-card {
            position: absolute;
            inset: 120px;
            background: linear-gradient(90deg, #000 0 20%, #888 20% 80%, #fff 80%);
          }
          .cover-kicker { color: #222; font: 32px sans-serif; }
          .cover-title {
            width: 800px;
            color: #888;
            font: 96px/1.2 sans-serif;
            text-align: center;
          }
        </style>
      </head>
      <body>
        <div class="slide slide-cover">
          <div class="cover-title-card">
            <div class="cover-kicker">生活分享</div>
            <div class="cover-title">看不见的标题</div>
          </div>
        </div>
      </body>
    </html>
    """
    monkeypatch.setattr(
        qa,
        "render_article_slides",
        lambda _manifest_path: ([("01-cover.png", locally_low_contrast_cover)], {}),
    )

    issues = qa._render_issues(tmp_path / "manifest.json")

    assert any(issue.code == "cover_low_contrast" for issue in issues)


def test_blank_manifest_defaults_fall_back_to_project_config(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("正文内容。\n", encoding="utf-8")
    (tmp_path / "markdown-to-image.config.yml").write_text(
        "nickname: 配置昵称\n"
        "bio: 配置简介\n"
        "chars_per_slide: 180\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "空字段测试",
                "social_title": "空字段应该回落到配置",
                "cta_line1": "结束语。",
                "nickname": "",
                "bio": "",
                "chars_per_slide": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert "@配置昵称" in rendered
    assert "配置简介" in rendered
    assert '<div class="end-handle">@</div>' not in rendered


def test_project_root_from_config_resolves_repo_relative_source(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    project_root.mkdir()
    article_path = project_root / "content" / "article.md"
    article_path.parent.mkdir()
    article_path.write_text("正文内容。\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "markdown-to-image.config.yml").write_text(
        f"project_root: {project_root}\n"
        "nickname: 配置昵称\n",
        encoding="utf-8",
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": "content/article.md",
                "original_title": "配置根目录测试",
                "social_title": "配置根目录可以解析文章",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, output_dir = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert output_dir == manifest_path.parent
    assert "配置根目录可以解析文章" in rendered


def test_x_platform_renders_title_inside_first_body_image_without_cover_or_end(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text(
        "这是一段适合发布到 X 的长正文。" * 260,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "platform": "x",
                "source": str(article_path),
                "original_title": "X 平台原始标题",
                "social_title": "X 平台四图长文标题",
                "nickname": "我要改名叫嘟嘟",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    names = [name for name, _ in slides]
    rendered = "\n".join(html for _, html in slides)

    assert names == ["01.png", "02.png", "03.png", "04.png"]
    assert all(not name.endswith("-end.png") for name in names)
    assert "01-cover.png" not in names
    assert "X 平台四图长文标题" in slides[0][1]
    assert '<div class="x-article-title">X 平台四图长文标题</div>' in slides[0][1]
    assert '<div class="x-article-title">' not in slides[1][1]
    assert "X 平台四图长文标题" not in slides[1][1]
    assert "--slide-height: 1440px" not in rendered


def test_x_platform_skips_article_image_blocks_by_default(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text(
        "第一段正文。\n\n"
        "![不会占用 X 图片额度](missing-image.jpg)\n\n"
        "第二段正文。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "platform": "x",
                "source": str(article_path),
                "original_title": "图片跳过测试",
                "social_title": "X 模式默认只渲染正文",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert [name for name, _ in slides] == ["01.png"]
    assert "第一段正文" in rendered
    assert "第二段正文" in rendered
    assert "missing-image.jpg" not in rendered
    assert "不会占用 X 图片额度" not in rendered


def test_x_platform_can_inline_article_images_when_enabled(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    article_dir = project_root / "content"
    image_dir = project_root / "static" / "images"
    article_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    (image_dir / "photo.jpg").write_bytes(
        (ROOT / "skills" / "markdown-to-image" / "examples" / "wygmjdd-article" / "images" / "001.jpg").read_bytes()
    )
    article_path = article_dir / "article.md"
    article_path.write_text(
        "第一段正文，图片之前还有文字。\n\n"
        '<figure><img src="/images/photo.jpg" alt="现场照片" />'
        "<figcaption>电影广告很多，而看电影竟然真的送加多宝</figcaption></figure>\n\n"
        "第二段正文，图片之后继续讲述。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "platform": "x",
                "source": "content/article.md",
                "project_root": str(project_root),
                "original_title": "X 内嵌图片测试",
                "social_title": "X 可以把图片合成进正文",
                "x_include_images": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert [name for name, _ in slides] == ["01.png"]
    assert "第一段正文" in rendered
    assert "第二段正文" in rendered
    assert "article-inline-image" in rendered
    assert "电影广告很多" in rendered
    assert "data:image/jpeg;base64," in rendered
    assert '<div class="article-photo-card">' not in rendered


def test_x_include_images_can_come_from_project_config(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    article_dir = project_root / "content"
    image_dir = project_root / "static" / "images"
    article_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    (image_dir / "photo.jpg").write_bytes(
        (ROOT / "skills" / "markdown-to-image" / "examples" / "wygmjdd-article" / "images" / "001.jpg").read_bytes()
    )
    (project_root / "markdown-to-image.config.yml").write_text(
        "platform: x\n"
        "x_include_images: true\n",
        encoding="utf-8",
    )
    article_path = article_dir / "article.md"
    article_path.write_text(
        "配置前文。\n\n"
        '![配置图片](/images/photo.jpg)\n\n'
        "配置后文。\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": "content/article.md",
                "project_root": str(project_root),
                "original_title": "配置图片测试",
                "social_title": "配置可以默认开启 X 内嵌图",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert [name for name, _ in slides] == ["01.png"]
    assert "配置前文" in rendered
    assert "配置后文" in rendered
    assert "article-inline-image" in rendered
    assert "data:image/jpeg;base64," in rendered


def test_x_inline_images_can_grow_height_to_reduce_sparse_image_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    render = _import_render_module()
    parser = _import_parser_module()
    blocks = [
        parser.ContentBlock("paragraph", "图片前正文。" * 20),
        parser.ContentBlock("image", "图片说明", image_src="photo.jpg"),
        parser.ContentBlock("paragraph", "图片后正文。" * 20),
    ]

    def fake_paginate_blocks_with_browser(body_blocks, render_page_html, *, max_chars):
        html = render_page_html([body_blocks[0]], 1, 0, [[body_blocks[0]]])
        marker = "--slide-height: "
        slide_height = int(html.split(marker, 1)[1].split("px", 1)[0])
        if slide_height < 1600:
            return [[body_blocks[0]], [body_blocks[1]], [body_blocks[2]], [body_blocks[2].with_text("尾段")]]
        return [[body_blocks[0], body_blocks[1]], [body_blocks[2]], [body_blocks[2].with_text("尾段")]]

    monkeypatch.setattr(render, "paginate_blocks_with_browser", fake_paginate_blocks_with_browser)

    pages, slide_height = render._paginate_x_body_pages(
        blocks,
        "标题",
        "作者",
        Path("article.md"),
        None,
        prefer_inline_image_fit=True,
    )

    assert slide_height == 1600
    assert len(pages) == 3
    assert pages[0][1].kind == "image"


def test_project_config_can_supply_default_x_platform(tmp_path: Path) -> None:
    render = _import_render_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("配置平台正文。\n", encoding="utf-8")
    (tmp_path / "markdown-to-image.config.yml").write_text(
        "platform: x\n"
        "nickname: 配置昵称\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": str(article_path),
                "original_title": "配置平台测试",
                "social_title": "配置可以默认选择 X",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert [name for name, _ in slides] == ["01.png"]
    assert "配置可以默认选择 X" in slides[0][1]
    assert "@配置昵称" in rendered


def test_x_platform_estimate_only_skips_legacy_static_pagination_warnings(tmp_path: Path) -> None:
    qa = _import_qa_module()
    article_path = tmp_path / "article.md"
    article_path.write_text("很短的 X 正文。\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "platform": "x",
                "source": str(article_path),
                "original_title": "X 估算测试",
                "social_title": "X estimate-only 不应该跑旧分页估算",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    issues = qa.audit_article_manifest(manifest_path, include_render=False)

    assert issues == []


def test_config_in_project_root_applies_to_nested_output_manifest(tmp_path: Path) -> None:
    render = _import_render_module()
    project_root = tmp_path / "site"
    article_path = project_root / "content" / "article.md"
    output_dir = project_root / "static" / "red-images" / "articles" / "nested"
    article_path.parent.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    article_path.write_text("正文内容。\n", encoding="utf-8")
    (project_root / "markdown-to-image.config.yml").write_text(
        f"project_root: {project_root}\n"
        "nickname: 项目根昵称\n"
        "bio: 项目根简介\n",
        encoding="utf-8",
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "source": "content/article.md",
                "original_title": "嵌套输出测试",
                "social_title": "项目根配置可以被嵌套输出读取",
                "cta_line1": "结束语。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    slides, _ = render.render_article_slides(manifest_path)
    rendered = "\n".join(html for _, html in slides)

    assert "@项目根昵称" in rendered
    assert "项目根简介" in rendered
