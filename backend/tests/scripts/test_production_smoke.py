"""Task O4：生产 smoke 分层脚本测试（dry-run / 付费门禁）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = REPO_ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
MOLIZHISHU_SCRIPT = REPO_ROOT / "backend" / "scripts" / "molizhishu_smoke_test.py"
PRODUCTION_SMOKE_SCRIPT = REPO_ROOT / "backend" / "scripts" / "run_production_smoke_test.py"


def _run_script(script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if env:
        merged.update(env)
    return subprocess.run(
        [str(PYTHON), str(script.relative_to(REPO_ROOT)), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=merged,
    )


def test_molizhishu_smoke_dry_run_without_token_fails():
    result = _run_script(
        MOLIZHISHU_SCRIPT,
        env={
            "MOLIZHISHU_ENABLED": "false",
            "MOLIZHISHU_API_TOKEN": "",
        },
    )
    assert result.returncode != 0
    assert "MOLIZHISHU" in (result.stdout + result.stderr)


def test_molizhishu_smoke_default_is_dry_run_without_paid_calls():
    result = _run_script(
        MOLIZHISHU_SCRIPT,
        env={
            "MOLIZHISHU_ENABLED": "true",
            "MOLIZHISHU_API_TOKEN": "test-smoke-token-value",
        },
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "dry-run" in output.lower() or "Dry-run" in output or "预检" in output
    assert "test-smoke-token-value" not in output
    assert "--allow-paid-provider" in output


def test_molizhishu_smoke_rejects_paid_without_explicit_flag():
    result = _run_script(
        MOLIZHISHU_SCRIPT,
        "--allow-paid-provider",
        env={
            "MOLIZHISHU_ENABLED": "true",
            "MOLIZHISHU_API_TOKEN": "test-smoke-token-value",
            "MOLIZHISHU_BASE_URL": "https://molizhishu.invalid.test",
        },
    )
    output = result.stdout + result.stderr
    assert "test-smoke-token-value" not in output
    assert result.returncode != 0 or "真实" in output or "adapter" in output.lower()


def test_production_smoke_default_preflight_only():
    result = _run_script(
        PRODUCTION_SMOKE_SCRIPT,
        env={
            "MOLIZHISHU_ENABLED": "false",
            "MOLIZHISHU_API_TOKEN": "",
            "AGENT_LLM_API_KEY": "",
        },
    )
    output = result.stdout + result.stderr
    assert "preflight" in output.lower() or "预检" in output
    assert "business-loop" in output.lower()
    assert result.returncode != 0


def test_production_smoke_business_loop_requires_allow_paid_flag():
    result = _run_script(
        PRODUCTION_SMOKE_SCRIPT,
        "--business-loop",
        env={
            "MOLIZHISHU_ENABLED": "true",
            "MOLIZHISHU_API_TOKEN": "test-smoke-token-value",
        },
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "allow-paid-provider" in output.lower() or "allow_paid" in output.lower()
    assert "test-smoke-token-value" not in output


def test_production_smoke_output_redacts_secrets():
    result = _run_script(
        PRODUCTION_SMOKE_SCRIPT,
        env={
            "MOLIZHISHU_ENABLED": "true",
            "MOLIZHISHU_API_TOKEN": "super-secret-molizhishu-token-xyz",
            "AGENT_LLM_API_KEY": "super-secret-agent-key-xyz",
        },
    )
    output = result.stdout + result.stderr
    assert "super-secret-molizhishu-token-xyz" not in output
    assert "super-secret-agent-key-xyz" not in output
