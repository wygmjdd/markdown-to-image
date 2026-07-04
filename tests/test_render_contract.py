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


def _import_cli_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import render_markdown_to_image

    return render_markdown_to_image


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

    assert "background-image" not in slides[0][1]


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
