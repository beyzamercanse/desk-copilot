"""HTTP API: POST /ask {"question": "..."}"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from desk_copilot.agent import ask

app = FastAPI(title="Desk Copilot")


class Question(BaseModel):
    question: str


@app.post("/ask")
def ask_endpoint(q: Question) -> dict:
    state = ask(q.question)
    usage = state.get("usage")
    return {
        "answer": state.get("answer"),
        "route": state.get("route"),
        "metric": state.get("metric"),
        "sql": state.get("sql"),
        "refused": bool(state.get("refused")),
        "latency_ms": round(usage.latency_ms, 1) if usage else None,
        "cost_usd": round(usage.cost_usd, 6) if usage else None,
    }
