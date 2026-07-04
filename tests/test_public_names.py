from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_skill_does_not_expose_legacy_xhs_api_names() -> None:
    prohibited = {
        "load_xhs_config",
        "strip_body_for_xhs",
        "xhs_title",
        "scripts/xhs/config.yml",
    }
    paths = [
        *sorted((ROOT / "skills").rglob("*.md")),
        *sorted((ROOT / "skills").rglob("*.py")),
        *sorted((ROOT / "skills").rglob("*.json")),
        *[
            path
            for path in sorted((ROOT / "tests").rglob("*.py"))
            if path.name != "test_public_names.py"
        ],
    ]
    offenders: list[str] = []

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for needle in prohibited:
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {needle}")

    assert offenders == []


def test_public_docs_do_not_contain_local_machine_paths() -> None:
    paths = [
        *sorted(ROOT.glob("README*.md")),
        *sorted((ROOT / "skills").rglob("*.md")),
        *sorted((ROOT / "skills").rglob("*.json")),
    ]
    offenders = [
        str(path.relative_to(ROOT))
        for path in paths
        if "/Users/" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_readmes_include_language_switches() -> None:
    english_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese_readme_path = ROOT / "README.zh-CN.md"

    assert chinese_readme_path.is_file()
    chinese_readme = chinese_readme_path.read_text(encoding="utf-8")
    assert "[简体中文](README.zh-CN.md)" in english_readme
    assert "[English](README.md)" in chinese_readme


def test_readme_describes_skill_as_agent_skill_not_codex_only() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    codex_only_phrases = {
        "Installable Codex skill",
        "Recommended Usage With Codex",
        "Codex should",
        "when using Codex",
        "written by Codex",
    }

    offenders = [phrase for phrase in sorted(codex_only_phrases) if phrase in readme]

    assert offenders == []
