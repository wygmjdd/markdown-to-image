from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_repo_exposes_installable_markdown_to_image_skill() -> None:
    skill_file = ROOT / "skills" / "markdown-to-image" / "SKILL.md"

    assert skill_file.is_file()

    text = skill_file.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, frontmatter, body = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)

    assert metadata["name"] == "markdown-to-image"
    assert "Markdown" in metadata["description"]
    assert "image" in metadata["description"].lower()
    assert "render_markdown_to_image.py" in body


def test_skill_bundles_renderer_script_and_package() -> None:
    skill_root = ROOT / "skills" / "markdown-to-image"

    assert (skill_root / "scripts" / "render_markdown_to_image.py").is_file()
    assert (skill_root / "scripts" / "requirements.txt").is_file()
    assert (skill_root / "scripts" / "markdown_to_image" / "render.py").is_file()
    assert (skill_root / "agents" / "openai.yaml").is_file()


def test_wygmjdd_article_example_is_complete_and_self_contained() -> None:
    example_root = ROOT / "skills" / "markdown-to-image" / "examples" / "wygmjdd-article"
    expected_files = {
        "article.md",
        "manifest.json",
        "post-caption.md",
        "01-cover.png",
        "02.png",
        "03.png",
        "04.png",
        "05.png",
        "06.png",
        "07.png",
        "08-end.png",
        "images/001.jpg",
        "images/002.jpg",
    }

    missing = [name for name in sorted(expected_files) if not (example_root / name).is_file()]
    assert missing == []

    manifest = json.loads((example_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "article.md"
    assert "project_root" not in manifest
    assert manifest["original_title"] == "15岁带弟弟上坡挖洋芋，20年后再来一次"
    assert manifest["social_title"] == "上坡挖洋芋时，母亲连说五个谜语，我突然一点不累了"
    assert manifest["cta_line1"] == "那时节，我忽然觉得已经很是疲倦的身体，似乎一点累也感受不到了。"

    article = (example_root / "article.md").read_text(encoding="utf-8")
    assert 'src="images/001.jpg"' in article
    assert 'src="images/002.jpg"' in article
