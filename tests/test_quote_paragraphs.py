from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "markdown-to-image" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from markdown_to_image.browser_paginator import _normalize_sources
from markdown_to_image.parser import ContentBlock, parse_body_blocks
from markdown_to_image.render import _render_body_page, _render_quote_group_html


def test_quote_paragraphs_keep_one_visual_group() -> None:
    block = ContentBlock("quote", "第一段。\n\n第二段。")

    paragraphs = _normalize_sources([block])

    assert [paragraph.text for paragraph in paragraphs] == ["第一段。", "第二段。"]
    assert paragraphs[0].source_id != paragraphs[1].source_id
    assert paragraphs[0].quote_group_id == 0
    assert paragraphs[1].quote_group_id == 0

    rendered = _render_quote_group_html(paragraphs)
    assert rendered.count('class="article-quote"') == 1
    assert rendered.count('class="article-quote-p"') == 2
    assert "第一段。" in rendered
    assert "第二段。" in rendered


def test_single_paragraph_quote_is_unchanged() -> None:
    block = ContentBlock("quote", "只有一段。")

    paragraphs = _normalize_sources([block])

    assert len(paragraphs) == 1
    assert paragraphs[0].text == "只有一段。"


def test_markdown_quote_paragraphs_survive_body_render_pipeline() -> None:
    blocks = parse_body_blocks("> 第一段。\n>\n> 第二段。")

    assert len(blocks) == 1
    assert blocks[0].kind == "quote"
    assert blocks[0].text == "第一段。\n\n第二段。"

    paragraphs = _normalize_sources(blocks)
    rendered = _render_body_page(
        "测试标题",
        paragraphs,
        page=1,
        total=1,
        nickname="测试作者",
    )

    assert rendered.count('class="article-quote"') == 1
    assert rendered.count('class="article-quote-p"') == 2
    assert rendered.index("第一段。") < rendered.index("第二段。")
