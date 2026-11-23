import json
from pathlib import Path

from desk_copilot.catalogue import load_catalogue

GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden_set.jsonl"
ROUTES = {"metric", "sql", "rag", "refuse"}


def cases():
    return [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]


def test_golden_cases_are_well_formed():
    ids = [c["id"] for c in cases()]
    assert len(ids) == len(set(ids))
    for case in cases():
        assert case["expected_route"] in ROUTES
        assert case["question"].strip()


def test_metric_cases_point_at_real_metrics_with_all_params():
    catalogue = load_catalogue()
    for case in cases():
        if case["expected_route"] != "metric":
            continue
        metric = catalogue.get(case["expected_metric"])
        assert set(case["expected_params"]) == set(metric.params), case["id"]


def test_every_route_is_covered():
    assert {c["expected_route"] for c in cases()} == ROUTES
