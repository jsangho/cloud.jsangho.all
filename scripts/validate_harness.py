#!/usr/bin/env python3
"""
Harness Validator — Star Topology Ontology Checker
===================================================
Karpathy 하네스 엔지니어링 원칙 적용:
  MD 파일의 frontmatter(type, links)를 파싱하여 스타 토폴로지 위반을 탐지한다.

검사 항목:
  1. frontmatter 누락 또는 필수 필드(type) 없음
  2. hub가 2개 이상 선언됨
  3. 스포크 → 스포크 직접 링크 (순환 참조 포함)
  4. 고립 노드 (링크가 전혀 없는 노드)
  5. 존재하지 않는 노드를 가리키는 dead link

사용법:
  python scripts/validate_harness.py [--docs-dir <경로>]
  기본 경로: _docs/  (Obsidian WikiLink [[filename]] 형식 파싱)
"""

import argparse
import re
import sys
from pathlib import Path

import yaml


# ──────────────────────────────────────────────
# 파서
# ──────────────────────────────────────────────

def parse_frontmatter(path: Path) -> dict | None:
    """YAML frontmatter(--- ... ---) 파싱. 없으면 None 반환."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None


def extract_wikilinks(path: Path) -> list[str]:
    """Obsidian WikiLink [[target]] 파싱. 앨리어스 [[target|alias]] 처리."""
    text = path.read_text(encoding="utf-8")
    # frontmatter 제거 후 본문만 검사
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", body)


# ──────────────────────────────────────────────
# 토폴로지 로드
# ──────────────────────────────────────────────

def load_topology(docs_dir: Path) -> dict:
    """docs_dir 내 모든 MD 파일을 읽어 노드 맵 구성."""
    nodes: dict[str, dict] = {}

    for md_file in docs_dir.rglob("*.md"):
        stem = md_file.stem
        frontmatter = parse_frontmatter(md_file)
        links = extract_wikilinks(md_file)
        nodes[stem] = {
            "path": md_file,
            "frontmatter": frontmatter,
            "links": links,
            "type": (frontmatter or {}).get("type"),  # "hub" | "spoke" | None
        }

    return nodes


# ──────────────────────────────────────────────
# 검증 규칙
# ──────────────────────────────────────────────

class Violation:
    def __init__(self, rule: str, node: str, detail: str):
        self.rule = rule
        self.node = node
        self.detail = detail

    def __str__(self):
        return f"[{self.rule}] {self.node}: {self.detail}"


def check_missing_frontmatter(nodes: dict) -> list[Violation]:
    violations = []
    for name, node in nodes.items():
        if node["frontmatter"] is None:
            violations.append(Violation("MISSING_FRONTMATTER", name, "frontmatter 없음"))
        elif node["type"] not in ("hub", "spoke"):
            violations.append(
                Violation("MISSING_TYPE", name, f"type 필드가 없거나 잘못됨: {node['type']!r}")
            )
    return violations


def check_single_hub(nodes: dict) -> list[Violation]:
    hubs = [n for n, v in nodes.items() if v["type"] == "hub"]
    if len(hubs) > 1:
        return [Violation("MULTIPLE_HUBS", ", ".join(hubs), f"허브는 하나여야 함. 발견: {hubs}")]
    if len(hubs) == 0:
        return [Violation("NO_HUB", "(전체)", "허브가 선언된 노드가 없음")]
    return []


def check_spoke_to_spoke(nodes: dict) -> list[Violation]:
    """스포크에서 다른 스포크로의 직접 링크 금지."""
    spoke_names = {n for n, v in nodes.items() if v["type"] == "spoke"}
    violations = []
    for name in spoke_names:
        for link in nodes[name]["links"]:
            if link in spoke_names and link != name:
                violations.append(
                    Violation("SPOKE_TO_SPOKE", name, f"스포크 직접 링크 금지: [[{link}]]")
                )
    return violations


def check_dead_links(nodes: dict) -> list[Violation]:
    all_names = set(nodes.keys())
    violations = []
    for name, node in nodes.items():
        for link in node["links"]:
            if link not in all_names:
                violations.append(
                    Violation("DEAD_LINK", name, f"존재하지 않는 노드 참조: [[{link}]]")
                )
    return violations


def check_isolated_nodes(nodes: dict) -> list[Violation]:
    """링크가 전혀 없고, 다른 노드에서도 참조되지 않는 고립 노드 탐지."""
    all_linked = {link for node in nodes.values() for link in node["links"]}
    violations = []
    for name, node in nodes.items():
        if not node["links"] and name not in all_linked:
            violations.append(Violation("ISOLATED_NODE", name, "연결된 링크가 전혀 없는 고립 노드"))
    return violations


def check_circular_references(nodes: dict) -> list[Violation]:
    """DFS로 순환 참조 탐지."""
    violations = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(node: str, path: list[str]) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbor in nodes.get(node, {}).get("links", []):
            if neighbor not in nodes:
                continue
            if neighbor not in visited:
                if dfs(neighbor, path + [neighbor]):
                    return True
            elif neighbor in rec_stack:
                cycle = " → ".join(path + [neighbor])
                violations.append(Violation("CIRCULAR_REF", node, f"순환 참조: {cycle}"))
                return True
        rec_stack.discard(node)
        return False

    for name in nodes:
        if name not in visited:
            dfs(name, [name])

    return violations


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def run(docs_dir: Path) -> int:
    if not docs_dir.exists():
        print(f"ERROR: docs 디렉토리를 찾을 수 없음: {docs_dir}", file=sys.stderr)
        return 1

    nodes = load_topology(docs_dir)
    if not nodes:
        print(f"WARNING: {docs_dir} 에 MD 파일이 없음")
        return 0

    all_violations: list[Violation] = []
    all_violations += check_missing_frontmatter(nodes)
    all_violations += check_single_hub(nodes)
    all_violations += check_spoke_to_spoke(nodes)
    all_violations += check_dead_links(nodes)
    all_violations += check_isolated_nodes(nodes)
    all_violations += check_circular_references(nodes)

    print(f"\n=== Harness Validator ({docs_dir}) ===")
    print(f"노드 수: {len(nodes)}")

    if not all_violations:
        print("✓ 모든 검사 통과 — 스타 토폴로지 무결성 확인")
        return 0

    print(f"\n✗ 위반 {len(all_violations)}건:\n")
    for v in all_violations:
        print(f"  {v}")

    return 1


def main():
    parser = argparse.ArgumentParser(description="Star Topology Harness Validator")
    parser.add_argument(
        "--docs-dir",
        default="_docs",
        help="검사할 MD 파일 디렉토리 (기본값: _docs)",
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    docs_dir = root / args.docs_dir
    sys.exit(run(docs_dir))


if __name__ == "__main__":
    main()
