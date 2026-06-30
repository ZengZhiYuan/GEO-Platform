"""Shared LLM/analysis hooks for tests that trigger async analyze API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from tests.geo_monitoring.agents.test_graph import FakeLLMClient


def patch_fake_llm_for_analyze(monkeypatch) -> FakeLLMClient:
    llm = FakeLLMClient()
    for target in (
        "app.geo_monitoring.services.analysis.create_agent_llm_client",
        "app.worker.actors.analysis.create_agent_llm_client",
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
    ):
        monkeypatch.setattr(target, lambda *_args, **_kwargs: llm)

    from app.worker.actors import analysis as analysis_actor

    def _analyze_run_sync(run_id: int) -> None:
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(analysis_actor.analyze_run, run_id).result()

    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.analyze_run.send",
        _analyze_run_sync,
    )
    return llm
