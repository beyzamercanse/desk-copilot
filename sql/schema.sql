-- Runs once when the Postgres container starts (docker-entrypoint-initdb.d).
create extension if not exists vector;

create table if not exists outage_notices (
    notice_id       text primary key,
    zone            text not null,
    unit_name       text,
    fuel_type       text,
    unavailable_mw  double precision,
    start_utc       timestamptz,
    end_utc         timestamptz,
    notice_text     text not null,
    embedding       vector(384) not null
);

create index if not exists outage_notices_embedding_idx
    on outage_notices using hnsw (embedding vector_cosine_ops);

-- The agent connects as this role: SELECT only, nothing else.
do $$
begin
    if not exists (select from pg_roles where rolname = 'copilot_readonly') then
        create role copilot_readonly login password 'readonly';
    end if;
end $$;

grant connect on database desk to copilot_readonly;
grant usage on schema public to copilot_readonly;
grant select on all tables in schema public to copilot_readonly;
alter default privileges in schema public grant select on tables to copilot_readonly;
