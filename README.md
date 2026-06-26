# kaoseghis-pacs

kaoseghis-pacs is a lightweight Windows-first Python agent that reads active imaging worklist rows from local eGHIS PostgreSQL and sends prepared entries to `kaos-mwl`.

## Highlights

- Read-only PostgreSQL 9.2-compatible polling of `public.mwl`.
- Join with `public.h2opd_doct_ord` via `eghis_key`.
- Route worklist rows to:
  - `BMD` (modality `BMD`, AE `BMD`)
  - `INNOVISION` (for DR, modality `CR`, AE `INNOVISION`)
- Local state hash-based dedup (no repeated POST in unchanged cycles).
- Runtime modes: `poll-once`, `poll-loop`, `test-post`.
- Dedicated safe `dry-run` mode.

## Files

- `src/kaoseghis_pacs/main.py` – CLI and orchestration
- `src/kaoseghis_pacs/db.py` – DB access (`public.mwl`, read-only)
- `src/kaoseghis_pacs/routing.py` – routing rules
- `src/kaoseghis_pacs/payload.py` – payload builders and hashing
- `src/kaoseghis_pacs/sync_client.py` – HTTP sync client
- `src/kaoseghis_pacs/state.py` – local payload dedup state
- `config/order_routing.example.json` – routing config
- `requirements.txt`
- `run-*.bat`

## Setup (Windows EMR Desktop)

1. Install Python 3.10+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill real credentials.
4. Run dry-run first:

```powershell
run-dry-run.bat
```

## Modes

- Poll once and exit:

```powershell
run-poll-once.bat
```

- Poll repeatedly every `POLL_INTERVAL_SECONDS`:

```powershell
run-poll-loop.bat
```

- Send sample payload:

```powershell
python -m kaoseghis_pacs test-post
```

## Config

Use `.env`:

- `EGHIS_DB_HOST`
- `EGHIS_DB_PORT`
- `EGHIS_DB_NAME`
- `EGHIS_DB_USER`
- `EGHIS_DB_PASSWORD`
- `KAOS_MWL_SYNC_URL`
- `POLL_INTERVAL_SECONDS`
- `TIMEZONE`
- `DRY_RUN`
- `ORDER_ROUTING_PATH`
- `STATE_PATH`
- `CONNECT_TIMEOUT_SECONDS`
- `QUERY_TIMEOUT_SECONDS`

## Safety

- DB is never mutated (no UPDATE/INSERT/DELETE/ALTER).
- Uses narrow SQL with explicit columns only.
- DB read failures stop POST for that cycle (fail-closed).
- Sensitive values (passwords, local DB config) come from `.env`.
