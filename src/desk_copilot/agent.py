"""LangGraph agent: route a desk question to a governed metric, a guarded SQL
query or outage-notice retrieval, then answer from the results only.

    question -> route -> metric | sql | rag -> answer
"""
from __future__ import annotations

import json
from typing import Any, TypedDict

from desk_copilot.catalogue import UndefinedMetric, load_catalogue
from desk_copilot.guardrails import GuardrailError, validate_sql
from desk_copilot.llm import Usage, complete


class State(TypedDict, total=False):
    question: str
    route: str
    metric: str | None
    params: dict[str, Any]
    sql: str | None
    rows: list[dict]
    passages: list[dict]
    answer: str
    refused: bool
    usage: Usage


CATALOGUE = load_catalogue()

ROUTER_SYSTEM = """You route questions from energy traders and risk analysts.
Reply with JSON only: {{"route": "metric" | "sql" | "rag" | "refuse", "metric": str | null, "params": {{}}}}.
- "metric" when one catalogue metric answers it; fill every parameter (dates as YYYY-MM-DD).
- "sql" only when no metric fits but the allowed tables can answer it.
- "rag" for questions about plant outages, unavailability or why supply changed.
- "refuse" when the question needs a definition that is not in the catalogue (for example VaR).
Catalogue:
{catalogue}
Allowed tables: {tables}"""

SQL_SYSTEM = """Write one PostgreSQL SELECT over these tables only: {tables}.
Use :name placeholders for values from the question. Reply with SQL only."""

ANSWER_SYSTEM = """Answer the desk's question in at most four sentences using only the data given.
Quote numbers with units (EUR, MWh, MW). If the data is empty, say so; never guess."""


def _route(state: State) -> State:
    system = ROUTER_SYSTEM.format(catalogue=CATALOGUE.describe(), tables=", ".join(sorted(CATALOGUE.tables)))
    text, usage = complete(system, state["question"], max_tokens=300)
    decision = json.loads(text)
    return {"route": decision["route"], "metric": decision.get("metric"), "params": decision.get("params", {}),
            "usage": state.get("usage", Usage()).add(usage)}


def _run_metric(state: State) -> State:
    from desk_copilot.db import run_query

    try:
        metric = CATALOGUE.get(state["metric"] or "")
    except UndefinedMetric:
        return {"refused": True, "answer": "That metric is not defined in the catalogue, so I won't estimate it."}
    sql = validate_sql(metric.sql, CATALOGUE.tables)
    return {"sql": sql, "rows": run_query(sql, state.get("params", {}))}


def _run_sql(state: State) -> State:
    from desk_copilot.db import run_query

    text, usage = complete(SQL_SYSTEM.format(tables=", ".join(sorted(CATALOGUE.tables))), state["question"])
    try:
        sql = validate_sql(text, CATALOGUE.tables)
    except GuardrailError as err:
        return {"refused": True, "answer": f"I can't run that query safely ({err}).",
                "usage": state["usage"].add(usage)}
    return {"sql": sql, "rows": run_query(sql, state.get("params", {})), "usage": state["usage"].add(usage)}


def _retrieve(state: State) -> State:
    from desk_copilot.rag import search

    return {"passages": search(state["question"])}


def _answer(state: State) -> State:
    if state.get("refused") or state.get("route") == "refuse":
        return {"answer": state.get("answer") or "That isn't defined in the metric catalogue, so I won't estimate it.",
                "refused": True}
    context = json.dumps({"rows": state.get("rows", []), "passages": state.get("passages", [])}, default=str)[:20_000]
    text, usage = complete(ANSWER_SYSTEM, f"Question: {state['question']}\nData: {context}")
    return {"answer": text, "usage": state["usage"].add(usage)}


def build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(State)
    graph.add_node("route", _route)
    graph.add_node("metric", _run_metric)
    graph.add_node("sql", _run_sql)
    graph.add_node("rag", _retrieve)
    graph.add_node("answer", _answer)
    graph.set_entry_point("route")
    graph.add_conditional_edges("route", lambda s: s["route"] if s["route"] in {"metric", "sql", "rag"} else "answer",
                                {"metric": "metric", "sql": "sql", "rag": "rag", "answer": "answer"})
    for node in ("metric", "sql", "rag"):
        graph.add_edge(node, "answer")
    graph.add_edge("answer", END)
    return graph.compile()


def ask(question: str) -> State:
    return build_graph().invoke({"question": question, "usage": Usage()})
