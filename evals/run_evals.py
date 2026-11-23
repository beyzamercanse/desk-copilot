"""Run the golden set and report routing accuracy, refusals, latency and cost.

    python evals/run_evals.py --min-accuracy 0.9

A question passes when the agent picks the expected route, metric and parameters
(or correctly refuses). Results go to evals/results.json for the CI summary.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from desk_copilot.agent import ask

HERE = Path(__file__).parent


def passed(case: dict, state: dict) -> bool:
    if case["expected_route"] == "refuse":
        return bool(state.get("refused"))
    if state.get("route") != case["expected_route"]:
        return False
    if case["expected_route"] == "metric":
        return state.get("metric") == case["expected_metric"] and state.get("params", {}) == case["expected_params"]
    return bool(state.get("answer"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-accuracy", type=float, default=0.9)
    args = parser.parse_args()

    cases = [json.loads(line) for line in (HERE / "golden_set.jsonl").read_text().splitlines() if line.strip()]
    results = []
    for case in cases:
        state = ask(case["question"])
        usage = state["usage"]
        results.append({"id": case["id"], "passed": passed(case, state), "route": state.get("route"),
                        "metric": state.get("metric"), "latency_ms": usage.latency_ms, "cost_usd": usage.cost_usd})

    accuracy = sum(r["passed"] for r in results) / len(results)
    summary = {
        "questions": len(results),
        "accuracy": round(accuracy, 3),
        "p50_latency_ms": round(statistics.median(r["latency_ms"] for r in results), 1),
        "mean_cost_usd": round(statistics.mean(r["cost_usd"] for r in results), 6),
        "failures": [r["id"] for r in results if not r["passed"]],
    }
    (HERE / "results.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(json.dumps(summary, indent=2))
    if accuracy < args.min_accuracy:
        raise SystemExit(f"accuracy {accuracy:.1%} below {args.min_accuracy:.0%}")


if __name__ == "__main__":
    main()
