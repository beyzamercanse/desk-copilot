"""Metric catalogue: the governed definitions the agent is allowed to use.

Each metric is a reviewed SQL query over the RiskLedger and GridFlow marts. The
agent picks a metric and its parameters; it never invents a business definition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "catalogue" / "metrics.yml"


class UndefinedMetric(KeyError):
    """The question asks for a metric that is not in the catalogue."""


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    sql: str
    params: tuple[str, ...] = ()


@dataclass
class Catalogue:
    tables: set[str]
    metrics: dict[str, Metric] = field(default_factory=dict)

    def get(self, name: str) -> Metric:
        try:
            return self.metrics[name]
        except KeyError as err:
            raise UndefinedMetric(name) from err

    def describe(self) -> str:
        """Compact text the router prompt uses to choose a metric."""
        lines = [f"- {m.name}({', '.join(m.params)}): {m.description}" for m in self.metrics.values()]
        return "\n".join(lines)


def load_catalogue(path: Path | str = DEFAULT_PATH) -> Catalogue:
    raw = yaml.safe_load(Path(path).read_text())
    metrics = {}
    for item in raw["metrics"]:
        if item["name"] in metrics:
            raise ValueError(f"duplicate metric: {item['name']}")
        metrics[item["name"]] = Metric(item["name"], item["description"].strip(), item["sql"].strip(),
                                       tuple(item.get("params", [])))
    return Catalogue(tables=set(raw["tables"]), metrics=metrics)
