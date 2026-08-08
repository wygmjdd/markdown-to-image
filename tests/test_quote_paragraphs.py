from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "markdown-to-image" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from markdown_to_image.browser_paginator import _normalize_sources, paginate_blocks_with_browser
from markdown_to_image.layout import (
    QUOTE_PARAGRAPH_GAP,
    estimate_block_height,
    page_content_height,
)
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


def test_adjacent_markdown_quote_blocks_render_as_one_continuous_group() -> None:
    blocks = parse_body_blocks(
        "> 第一段摘抄。\n\n"
        "> 第二段摘抄。\n\n"
        "> 第三段摘抄。\n"
    )

    normalized = _normalize_sources(blocks)
    assert len(normalized) == 3
    assert {block.quote_group_id for block in normalized} == {0}

    rendered = _render_body_page(
        "测试标题",
        normalized,
        page=1,
        total=1,
        nickname="测试作者",
    )
    assert rendered.count('class="article-quote"') == 1
    assert rendered.count('class="article-quote-p"') == 3
    assert page_content_height(normalized) == pytest.approx(
        sum(estimate_block_height(block) for block in normalized)
        + QUOTE_PARAGRAPH_GAP * 2
    )


def test_non_quote_block_starts_a_new_quote_group() -> None:
    normalized = _normalize_sources(
        [
            ContentBlock("quote", "第一组。"),
            ContentBlock("paragraph", "正文。"),
            ContentBlock("quote", "第二组。"),
        ]
    )

    quote_groups = [
        block.quote_group_id for block in normalized if block.kind == "quote"
    ]
    assert quote_groups == [0, 1]


def test_long_quotes_use_browser_height_instead_of_body_char_limit() -> None:
    quote = ContentBlock("quote", "这是一段需要连续排版的摘抄。" * 60)

    def render_probe(
        blocks: list[ContentBlock],
        total: int,
        page_index: int = 0,
        all_pages: list[list[ContentBlock]] | None = None,
    ) -> str:
        return _render_body_page(
            "测试标题",
            blocks,
            page=page_index + 1,
            total=max(total, 1),
            nickname="测试作者",
        )

    pages = paginate_blocks_with_browser([quote], render_probe, max_chars=100)

    assert len(pages) < len(quote.text) // 100
    assert len("".join(block.text for block in pages[0])) > 100


def test_continuous_long_quote_does_not_leave_an_orphan_tail_slide() -> None:
    paragraph = ("连续摘抄文字，" * 4)[:24] + "。"
    quotes = [ContentBlock("quote", paragraph) for _ in range(29)]

    def render_probe(
        blocks: list[ContentBlock],
        total: int,
        page_index: int = 0,
        all_pages: list[list[ContentBlock]] | None = None,
    ) -> str:
        return _render_body_page(
            "测试标题",
            blocks,
            page=page_index + 1,
            total=max(total, 1),
            nickname="测试作者",
        )

    pages = paginate_blocks_with_browser(quotes, render_probe, max_chars=100)

    assert len(pages) == 2
    assert min(sum(len(block.text) for block in page) for page in pages) >= 300
