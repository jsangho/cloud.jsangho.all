"""복구 런북이 **저장소와 어긋나지 않는지** 고정한다.

런북은 장애 중에 사람이 그대로 복사해 쓰는 문서다. 낡은 명령은 없는 명령보다 위험하다 —
2026-11-06 전까지 이 문서는 인증이 없는 커밋을 "현재 운영" 이라 적고 그리로 되돌리는
명령을 담고 있었다. 그래서 문서 속 명령을 꺼내 실제로 돌린다.

git 이력이 필요한 테스트는 얕은 체크아웃(CI)에서 skip 된다. 판본표는 전체 이력에서만
검증된다. 운영 EC2·운영 DB 에는 접속하지 않는다.
"""

from __future__ import annotations

import importlib.util
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from kayfabe.dependencies.career_sandbox_provider import (
    CAREER_V3_WRITES_ENV,
    career_v3_writes_enabled,
)

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[5]
_FASTAPI = _ROOT / "fastapi"
_APPS = _FASTAPI / "apps"
_RUNBOOK = _FASTAPI / "_docs" / "sandbox-career-recovery-runbook.md"
_TOOL = _APPS / "kayfabe" / "scripts" / "career_save_recovery.py"
_CODEC = "fastapi/apps/kayfabe/adapter/outbound/pg/career_world_codec.py"

#: Manager API 인증을 넣은 커밋. 이것을 품지 않는 대상으로 되돌리면 공개된다.
_MANAGER_AUTH = "72437d6"
_UNSAFE = ("8c965da", "e4702c0", "79ae8d8")
#: 쓰기 차단 Flag 를 넣은 커밋.
_FLAG = "7a3de79"
_SAFE = ("72437d6", "e2fc44b", _FLAG)


def _load_tool() -> Any:
    spec = importlib.util.spec_from_file_location("_career_recovery_doc", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load_tool()


def _text() -> str:
    return _RUNBOOK.read_text(encoding="utf-8")


def _bash_blocks() -> list[str]:
    return re.findall(r"```bash\n(.*?)```", _text(), flags=re.DOTALL)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_history(*commits: str) -> None:
    for commit in commits:
        if _git("cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
            pytest.skip(f"{commit} 이 없는 얕은 체크아웃이다")


def _block_with(marker: str) -> str:
    found = [block for block in _bash_blocks() if marker in block]
    assert len(found) == 1, marker
    return found[0]


def _guard() -> str:
    block = _block_with("# >>> rollback-guard")
    return block.split("# >>> rollback-guard\n")[1].split("# <<< rollback-guard")[0]


# ── 위험한 되돌리기 ──────────────────────────────────────────────


def test_no_command_moves_to_a_commit_without_manager_auth() -> None:
    forbidden = "|".join(_UNSAFE)
    pattern = re.compile(
        rf"(git\s+(switch|checkout|reset)\b.*({forbidden}))|(TARGET=({forbidden}))"
    )
    for block in _bash_blocks():
        for line in block.splitlines():
            assert not pattern.search(line), line
    assert "docker tag" not in _text()


def test_every_code_move_passes_through_the_guard() -> None:
    moves = [
        block
        for block in _bash_blocks()
        if re.search(r"git\s+(switch|checkout)\b", block) and "fastapi" not in block
    ]
    moves += [
        b for b in _bash_blocks() if "git switch --detach" in b and b not in moves
    ]
    assert moves, "되돌리기 명령이 사라졌다"
    for block in moves:
        assert block.index("# <<< rollback-guard") < block.index("git switch")
        assert 'git switch --detach "$TARGET"' in block


def test_the_warning_stands_above_everything() -> None:
    head = _text().split("## 0.")[0]
    assert "`8c965da` 로 되돌리지 않는다" in head
    assert "Manager API" in head
    assert "rollback-8c965da" in head


@pytest.mark.parametrize("target", _UNSAFE)
def test_the_guard_refuses_commits_without_manager_auth(target: str) -> None:
    _require_history(target, _MANAGER_AUTH)
    run = subprocess.run(
        ["bash", "-c", f"set -euo pipefail\nTARGET={target}\n{_guard()}"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1
    assert "REFUSED" in run.stdout and "Manager API" in run.stdout


@pytest.mark.parametrize("target", _SAFE)
def test_the_guard_allows_commits_with_manager_auth(target: str) -> None:
    _require_history(target)
    run = subprocess.run(
        ["bash", "-c", f"set -euo pipefail\nTARGET={target}\n{_guard()}"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_the_guard_refuses_an_unknown_commit() -> None:
    run = subprocess.run(
        ["bash", "-c", f"set -euo pipefail\nTARGET=0000000\n{_guard()}"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1 and "없는 커밋" in run.stdout


# ── 판본표 ───────────────────────────────────────────────────────


def _commit_table() -> dict[str, list[str]]:
    section = _text().split("### 0-2.")[1].split("격리 PG에서")[0]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        match = re.fullmatch(r"`([0-9a-f]{7})`", cells[0])
        if match:
            rows[match.group(1)] = cells
    return rows


def test_the_table_lists_exactly_the_known_commits() -> None:
    assert set(_commit_table()) == {*_UNSAFE, "e2fc44b", _FLAG}


@pytest.mark.parametrize("commit", (*_UNSAFE, "e2fc44b", _FLAG))
def test_the_table_matches_git(commit: str) -> None:
    _require_history(commit, _MANAGER_AUTH)
    row = _commit_table()[commit]
    source = _git("show", f"{commit}:{_CODEC}").stdout
    version = re.search(r"^SCHEMA_VERSION = (\d+)", source, flags=re.MULTILINE)
    assert version is not None and row[1] == version.group(1)

    has_auth = (
        _git("merge-base", "--is-ancestor", _MANAGER_AUTH, commit).returncode == 0
    )
    assert ("없음" not in row[3]) == has_auth
    assert ("금지" not in row[6]) == has_auth

    tool_path = "fastapi/apps/kayfabe/scripts/career_save_recovery.py"
    has_tool = _git("cat-file", "-e", f"{commit}:{tool_path}").returncode == 0
    assert (row[5] == "있음") == has_tool

    gate = _git("grep", "-c", CAREER_V3_WRITES_ENV, commit, "--", "fastapi/apps")
    assert (row[4] == "있음") == (gate.returncode == 0)


def test_the_recorded_production_commit_carries_manager_auth() -> None:
    assert "| 운영 백엔드 | `e2fc44b` |" in _text()
    _require_history("e2fc44b", _MANAGER_AUTH)
    assert _git("merge-base", "--is-ancestor", _MANAGER_AUTH, "e2fc44b").returncode == 0


def test_no_commit_placeholder_is_left() -> None:
    assert "<FLAG_SHA>" not in _text()
    assert "FLAG_SHA" not in _text()


def test_the_stale_production_claims_are_gone() -> None:
    text = _text()
    assert "현재 운영" not in text
    assert "extract_backup_phase1b" not in text
    assert "SHA256SUMS.phase1b" not in text


# ── 명령이 저장소와 맞는가 ───────────────────────────────────────


def _tool_commands() -> list[list[str]]:
    commands = []
    for block in _bash_blocks():
        for line in block.replace("\\\n", " ").splitlines():
            if "career_save_recovery.py" not in line or line.startswith("#"):
                continue
            tail = line.split("career_save_recovery.py", 1)[1]
            commands.append(shlex.split(tail.split("#", 1)[0]))
    return commands


def test_every_tool_command_parses() -> None:
    commands = _tool_commands()
    assert {command[0] for command in commands} == {
        "fingerprint",
        "downgrade-v3",
        "restore",
    }
    for command in commands:
        tool._parser().parse_args(command)


@pytest.mark.parametrize(
    "relative",
    (
        "fastapi/apps/kayfabe/scripts/career_save_recovery.py",
        "fastapi/apps/kayfabe/tests/scripts/career_save_audit.py",
        "fastapi/apps/kayfabe/tests/scripts/test_career_recovery_runbook.py",
        ".claude/skills/deploy/SKILL.md",
    ),
)
def test_named_files_exist_and_are_named(relative: str) -> None:
    assert (_ROOT / relative).is_file()
    assert relative.removeprefix("fastapi/") in _text()


def test_the_audit_command_matches_the_repository_layout() -> None:
    block = _block_with("career_save_audit.py")
    assert "cd fastapi" in block
    assert "PYTHONPATH=apps:. uv run python apps/kayfabe/tests/scripts/" in block


def test_server_paths_match_the_deploy_skill() -> None:
    skill = (_ROOT / ".claude/skills/deploy/SKILL.md").read_text(encoding="utf-8")
    assert "/home/ec2-user/cloud.jsangho.all" in skill
    assert "/home/ec2-user/cloud.jsangho.all" in _text()


def test_no_production_project_ref_is_published() -> None:
    assert not tool._contains_production_ref(_text())


def test_no_extra_alembic_or_build_step_is_implied() -> None:
    for block in _bash_blocks():
        assert "alembic upgrade" not in block
        assert "docker compose build" not in block
        assert "--build" not in block


# ── Flag 문구가 코드와 맞는가 ────────────────────────────────────


def test_the_flag_name_matches_the_code_and_the_template() -> None:
    assert CAREER_V3_WRITES_ENV == "CAREER_V3_WRITES_ENABLED"
    assert CAREER_V3_WRITES_ENV in _text()
    template = (_FASTAPI / ".env.example").read_text(encoding="utf-8")
    assert f"{CAREER_V3_WRITES_ENV}=false" in template


def _close_flag(env_dir: Path) -> None:
    block = _block_with("sed -i 's/^CAREER_V3_WRITES_ENABLED")
    script = block[block.index("if grep -q") : block.index("docker compose restart")]
    subprocess.run(["bash", "-c", script], cwd=env_dir, check=True)


@pytest.mark.parametrize(
    "before",
    (
        "A=1\nCAREER_V3_WRITES_ENABLED=true\nB=2\n",
        "A=1\nCAREER_V3_WRITES_ENABLED=true",
        "A=1\n",
        "A=1",
    ),
    ids=("open", "open-no-newline", "absent", "absent-no-newline"),
)
def test_the_close_command_writes_exactly_one_false_line(
    tmp_path: Path, before: str
) -> None:
    (tmp_path / "fastapi").mkdir()
    env = tmp_path / "fastapi" / ".env"
    env.write_text(before, encoding="utf-8")

    _close_flag(tmp_path)

    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines.count("CAREER_V3_WRITES_ENABLED=false") == 1
    assert "A=1" in lines
    assert not any(line.endswith("=true") for line in lines)


def test_deleting_the_line_does_not_close_but_false_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**런북이 줄 삭제를 금지하는 이유.** compose `env_file` 값이 살아남는다."""
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    env = tmp_path / ".env"

    env.write_text("OTHER=1\n", encoding="utf-8")
    load_dotenv(env, override=True)
    assert career_v3_writes_enabled() is True

    env.write_text(f"{CAREER_V3_WRITES_ENV}=false\n", encoding="utf-8")
    load_dotenv(env, override=True)
    assert career_v3_writes_enabled() is False


def test_the_flag_check_uses_names_that_exist() -> None:
    from core.matrix.vault_keymaker_secret_manager import Keymaker, get_keymaker

    assert callable(get_keymaker) and callable(Keymaker.load_env)
    block = _block_with("career_v3_writes_enabled")
    assert "get_keymaker().load_env()" in block
    assert "kayfabe.dependencies.career_sandbox_provider" in block


# ── 시나리오가 빠지지 않았는가 ───────────────────────────────────


@pytest.mark.parametrize("scenario", "ABCDE")
def test_each_scenario_separates_possible_from_impossible(scenario: str) -> None:
    text = _text().split("## 12.")[1]
    section = re.split(rf"### {scenario}\. ", text)[1].split("\n### ")[0]
    assert "✅" in section and "⛔" in section
