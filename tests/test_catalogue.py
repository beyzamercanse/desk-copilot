import pytest

from desk_copilot.catalogue import UndefinedMetric, load_catalogue
from desk_copilot.params import placeholders


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue()


def test_catalogue_loads_with_metrics(catalogue):
    assert len(catalogue.metrics) >= 9
    assert "fct_pnl_explain" in catalogue.tables


def test_declared_params_match_placeholders(catalogue):
    for metric in catalogue.metrics.values():
        assert placeholders(metric.sql) == set(metric.params), metric.name


def test_unknown_metric_is_refused(catalogue):
    with pytest.raises(UndefinedMetric):
        catalogue.get("var_99_10d")


def test_every_metric_passes_guardrails(catalogue):
    pytest.importorskip("sqlglot")
    from desk_copilot.guardrails import validate_sql

    for metric in catalogue.metrics.values():
        guarded = validate_sql(metric.sql, catalogue.tables)
        assert guarded.endswith("LIMIT 200")
