from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "markdown-to-image" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from markdown_to_image.browser_paginator import (
    _normalize_sources,
    _split_unit,
    paginate_blocks_with_browser,
)
from markdown_to_image.parser import ContentBlock, parse_body_blocks
from markdown_to_image.paginator import paginate_blocks, split_block_to_chunks
from markdown_to_image.render import _render_block_html, _render_body_page


def test_atx_headings_are_parsed_as_first_class_blocks() -> None:
    blocks = parse_body_blocks(
        "开头正文。\n"
        "## **一、武功起源**\n"
        "### **1、张三丰的武功修炼路径**\n"
        "路径正文。\n\n"
        "### **2、张无忌的武功修炼路径** ###\n"
        "## **二、我的推论**\n"
    )

    assert [block.kind for block in blocks] == [
        "paragraph",
        "heading",
        "heading",
        "paragraph",
        "heading",
        "heading",
    ]
    assert [(block.heading_level, block.text) for block in blocks if block.kind == "heading"] == [
        (2, "**一、武功起源**"),
        (3, "**1、张三丰的武功修炼路径**"),
        (3, "**2、张无忌的武功修炼路径**"),
        (2, "**二、我的推论**"),
    ]


def test_atx_heading_markers_do_not_render_as_visible_text() -> None:
    headings = parse_body_blocks(
        "## **一、武功起源**\n\n"
        "### **1、张三丰的武功修炼路径**\n"
    )

    html = _render_body_page(
        "张无忌打得过张三丰么？",
        headings,
        page=1,
        total=1,
        nickname="作者",
    )

    assert '<h2 class="article-heading article-heading-level-2">' in html
    assert '<h3 class="article-heading article-heading-level-3">' in html
    assert '<strong class="article-strong">一、武功起源</strong>' in html
    assert "## " not in html
    assert "### " not in html
    assert "**" not in html


def test_heading_blocks_are_not_split_or_merged_by_paginators() -> None:
    heading = ContentBlock(
        "heading",
        "**1、张三丰的武功修炼路径**" * 30,
        heading_level=3,
    )

    assert split_block_to_chunks(heading, max_chars=20) == [heading]
    assert _split_unit(heading, max_chars=20) == [heading]

    normalized = _normalize_sources(
        [
            ContentBlock("heading", "**一、武功起源**", heading_level=2),
            ContentBlock("heading", "**二、我的推论**", heading_level=2),
        ]
    )
    assert len(normalized) == 2
    assert normalized[0].source_id != normalized[1].source_id
    assert normalized[0].heading_level == normalized[1].heading_level == 2


def test_heading_stays_with_following_text_when_page_breaks() -> None:
    pages = paginate_blocks(
        [
            ContentBlock("paragraph", "前页正文。" * 79),
            ContentBlock("heading", "**二、我的推论**", heading_level=2),
            ContentBlock("heading", "**1、推论依据**", heading_level=3),
            ContentBlock("paragraph", "标题后的正文。" * 8),
        ],
        max_chars=1_000,
    )

    heading_page_index = next(
        index
        for index, page in enumerate(pages)
        if any(block.kind == "heading" for block in page)
    )
    heading_page = pages[heading_page_index]
    heading_index = next(
        index for index, block in enumerate(heading_page) if block.kind == "heading"
    )
    assert [block.kind for block in heading_page[heading_index:]] == [
        "heading",
        "heading",
        "paragraph",
    ]


def test_browser_paginator_keeps_long_heading_atomic_beyond_char_limit() -> None:
    heading = ContentBlock(
        "heading",
        "这是一个超过正文字符预算但能完整放进页面的标题",
        heading_level=2,
    )

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
            nickname="作者",
        )

    pages = paginate_blocks_with_browser([heading], render_probe, max_chars=20)

    assert pages == [[heading.with_text(heading.text, source_id=0)]]


def test_non_heading_hashes_remain_ordinary_text_or_code() -> None:
    blocks = parse_body_blocks(
        "这里讨论 # 号。\n\n"
        "    # 代码注释\n\n"
        "####### 七个井号不是 ATX 标题。\n"
    )

    assert [block.kind for block in blocks] == ["paragraph", "code", "paragraph"]
    assert blocks[0].text == "这里讨论 # 号。"
    assert blocks[1].text == "# 代码注释"
    assert blocks[2].text == "####### 七个井号不是 ATX 标题。"

    tab_blocks = parse_body_blocks("\t# Tab 缩进代码注释\n")
    assert [block.kind for block in tab_blocks] == ["code"]
    assert tab_blocks[0].text == "# Tab 缩进代码注释"


def test_heading_renderer_clamps_invalid_levels() -> None:
    block = ContentBlock("heading", "标题", heading_level=99)

    assert _render_block_html(block) == (
        '<h6 class="article-heading article-heading-level-6">标题</h6>'
    )
