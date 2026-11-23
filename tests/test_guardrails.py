import pytest

sqlglot = pytest.importorskip("sqlglot")

from desk_copilot.guardrails import GuardrailError, validate_sql  # noqa: E402
from desk_copilot.params import to_psycopg  # noqa: E402

ALLOWED = {"fct_pnl_explain", "gridflow.mart_price_spreads"}


def test_select_on_allowed_table_is_wrapped_in_a_limit():
    sql = validate_sql("select hub, sum(total_change_eur) from fct_pnl_explain group by hub", ALLOWED, max_rows=50)
    assert sql.startswith("SELECT * FROM (")
    assert sql.endswith("LIMIT 50")


def test_schema_qualified_table_is_allowed():
    validate_sql("select * from gridflow.mart_price_spreads", ALLOWED)


def test_cte_over_allowed_table_is_allowed():
    validate_sql("with x as (select * from fct_pnl_explain) select count(*) from x", ALLOWED)


@pytest.mark.parametrize("sql", [
    "delete from fct_pnl_explain",
    "drop table fct_pnl_explain",
    "update fct_pnl_explain set total_change_eur = 0",
    "insert into fct_pnl_explain values (1)",
])
def test_data_changing_statements_are_refused(sql):
    with pytest.raises(GuardrailError):
        validate_sql(sql, ALLOWED)


def test_multiple_statements_are_refused():
    with pytest.raises(GuardrailError):
        validate_sql("select 1 from fct_pnl_explain; drop table fct_pnl_explain", ALLOWED)


def test_unknown_table_is_refused():
    with pytest.raises(GuardrailError):
        validate_sql("select * from pg_catalog.pg_user", ALLOWED)


def test_placeholders_are_converted_but_casts_are_kept():
    out = to_psycopg("select * from t where d = :as_of_date and x::date = :as_of_date")
    assert out == "select * from t where d = %(as_of_date)s and x::date = %(as_of_date)s"
