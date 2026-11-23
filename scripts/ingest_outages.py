"""Load ENTSO-E generation-unit unavailability notices into pgvector.

    ENTSOE_API_KEY=... DATABASE_URL=postgresql://desk:desk@localhost:5432/desk \
        python scripts/ingest_outages.py --zone NL --start 2026-01-01 --end 2026-06-30
"""
from __future__ import annotations

import argparse
import os

import pandas as pd


# Column names follow entsoe-py's unavailability frame; print df.columns once and adjust
# these keys if your entsoe-py version names them differently.
def notice_text(row: pd.Series, zone: str) -> str:
    return (f"{row.get('production_resource_name', 'Unknown unit')} ({row.get('plant_type', 'unknown fuel')}) in {zone}: "
            f"{row.get('avail_qty', 'n/a')} MW available of {row.get('nominal_power', 'n/a')} MW nominal "
            f"from {row.get('start')} to {row.get('end')}; reason: {row.get('reason_text', 'not given')}.")


def main() -> None:
    from entsoe import EntsoePandasClient
    import psycopg
    from pgvector.psycopg import register_vector

    from desk_copilot.rag import embed

    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", default="NL")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-30")
    args = parser.parse_args()

    client = EntsoePandasClient(api_key=os.environ["ENTSOE_API_KEY"])
    start, end = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    df = client.query_unavailability_of_generation_units(args.zone, start=start, end=end).reset_index()
    texts = [notice_text(r, args.zone) for _, r in df.iterrows()]
    vectors = embed(texts)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        register_vector(conn)
        for i, (row, text, vec) in enumerate(zip(df.to_dict("records"), texts, vectors)):
            conn.execute(
                """insert into outage_notices
                   (notice_id, zone, unit_name, fuel_type, unavailable_mw, start_utc, end_utc, notice_text, embedding)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (notice_id) do update set notice_text = excluded.notice_text,
                                                         embedding = excluded.embedding""",
                (f"{args.zone}-{row.get('mrid', i)}-{row.get('revision', 0)}", args.zone,
                 row.get("production_resource_name"), row.get("plant_type"),
                 row.get("nominal_power"), row.get("start"), row.get("end"), text, vec),
            )
    print(f"loaded {len(texts)} notices for {args.zone}")


if __name__ == "__main__":
    main()
