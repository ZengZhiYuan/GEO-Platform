"""LangGraph 分析编排。"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.geo_monitoring.agents import nodes
from app.geo_monitoring.agents.llm import AgentLLMClient


class AnalysisState(TypedDict, total=False):
    run_id: int
    project_id: int
    prompt_set_version: str
    platform_codes: list[str]
    target_brand_id: int
    target_brand_name: str
    target_aliases: list[str]
    competitor_brand_ids: list[int]
    brand_names: dict[int, str]
    official_domain: str
    answers: list[dict[str, Any]]
    valid_answer_count: int
    platform_metrics: dict[str, dict[str, Any]]
    classifications: dict[str, dict[str, Any]]
    platform_insights: dict[str, dict[str, Any]]
    platform_failures: dict[str, list[str]]
    execution_records: list[dict[str, Any]]
    analysis_status: str
    skip_reason: str | None


# 加载数据后路由：无有效回答则跳过分析直接持久化
def _route_after_load(state: AnalysisState) -> str:
    if state.get("analysis_status") == "skipped":
        return "persist_results"
    return "calculate_metrics"


# 构建 LangGraph 分析流水线并编译为可执行图
def build_analysis_graph(*, db: Session, llm_client: AgentLLMClient):
    graph = StateGraph(AnalysisState)

    # 加载运行数据节点（注入数据库会话）
    def load_run_data(state: AnalysisState) -> AnalysisState:
        return nodes.load_run_data(state, db=db)

    # 计算确定性指标节点
    def calculate_metrics(state: AnalysisState) -> AnalysisState:
        return nodes.calculate_metrics(state)

    # LLM 回答分类节点
    def classify_answers(state: AnalysisState) -> AnalysisState:
        return nodes.classify_answers(state, llm_client=llm_client)

    # LLM 洞察生成节点
    def generate_insights(state: AnalysisState) -> AnalysisState:
        return nodes.generate_insights(state, llm_client=llm_client)

    # 分析结果持久化节点
    def persist_results(state: AnalysisState) -> AnalysisState:
        return nodes.persist_results(state, db=db)

    graph.add_node("load_run_data", load_run_data)
    graph.add_node("calculate_metrics", calculate_metrics)
    graph.add_node("classify_answers", classify_answers)
    graph.add_node("generate_insights", generate_insights)
    graph.add_node("persist_results", persist_results)

    graph.add_edge(START, "load_run_data")
    graph.add_conditional_edges(
        "load_run_data",
        _route_after_load,
        {
            "calculate_metrics": "calculate_metrics",
            "persist_results": "persist_results",
        },
    )
    graph.add_edge("calculate_metrics", "classify_answers")
    graph.add_edge("classify_answers", "generate_insights")
    graph.add_edge("generate_insights", "persist_results")
    graph.add_edge("persist_results", END)

    return graph.compile()
