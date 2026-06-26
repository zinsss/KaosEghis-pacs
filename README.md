# kaoseghis-pacs

kaoseghis-pacs is a lightweight Windows-first Python agent that reads active imaging worklist rows from local eGHIS PostgreSQL and sends prepared entries to `kaos-mwl`.

## Highlights

- Read-only PostgreSQL 9.2-compatible polling of `public.mwl`.
- Join with `public.h2opd_doct_ord` via `eghis_key`.
- Route worklist rows to:
  - `BMD` (modality `BMD`, AE `BMD`)
  - `INNOVISION` (for DR, modality `CR`, AE `INNOVISION`)
- Local state hash-based dedup (no repeated POST in unchanged cycles).
- Runtime modes: `poll-once`, `poll-loop`, `test-post`, `tray`, `manual`.
- Dedicated safe `dry-run` mode.

## Files

- `src/kaoseghis_pacs/main.py` – CLI and orchestration
- `src/kaoseghis_pacs/db.py` – DB access (`public.mwl`, read-only)
- `src/kaoseghis_pacs/routing.py` – routing rules
- `src/kaoseghis_pacs/payload.py` – payload builders and hashing
- `src/kaoseghis_pacs/sync_client.py` – HTTP sync client
- `src/kaoseghis_pacs/state.py` – local payload dedup state
- `src/kaoseghis_pacs/history.py` – tray/event history JSONL writer
- `src/kaoseghis_pacs/tray.py` – Windows system tray mode
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

- Windows tray mode (system tray UI + background polling):

```powershell
run-tray.bat
```

- Manual fallback mode (Windows-native form without DB access):

```powershell
run-manual.bat
```

- Manual mode is a fallback for environments where eGHIS DB access is unavailable.
- Manual mode writes a local `manual_*` history event stream and posts to `KAOS_MWL_SYNC_URL` using the kaos-mwl sync schema.
- It does not read or write eGHIS DB and does not require tray mode.

- Send sample payload:

```powershell
python -m kaoseghis_pacs test-post
```

## Tray mode

- Start with `run-tray.bat` or `python -m kaoseghis_pacs tray`.
- Tray menu includes:
  - Status (`Running`, `Dry-run`, `Error`)
  - Last poll time
  - Last POST result
  - Last routed count
  - Open today's history
  - Poll once now
  - Toggle dry-run
  - Exit
- Polling continues in background while tray menu remains available.

## Today's history

- History is written locally to:

```text
state/history-YYYYMMDD.jsonl
```

- Events are JSON lines and include:
  - `poll_started`
  - `poll_completed`
  - `routed_item`
  - `ignored_item`
  - `sync_posted`
  - `sync_failed`
  - `no_change`
- Each line includes event timestamp plus routing identifiers and status/result fields.

## Run without tray

```powershell
python -m kaoseghis_pacs poll-once
python -m kaoseghis_pacs poll-loop
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
