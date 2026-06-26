# Architecture Overview

## System purpose

`kaoseghis-pacs` polls active MWL rows, routes each row by configured business rules, and sends worklist sync payloads to a KAOS endpoint. It can run as a headless CLI loop or as a Windows tray app.

## Runtime modes

- `poll-once`: one pass and exit.
- `poll-loop`: periodic polling loop (`POLL_INTERVAL_SECONDS`).
- `test-post`: sends a sample payload.
- `tray`: keeps polling in a background thread while exposing status/history controls in the Windows system tray.

## Runtime flow (headless)

1. `main.py` parses CLI arguments and loads settings (`main.read_settings_from_env`).
2. `main.run_once`:
   - Builds DB config (`db.EGhisDbConfig`).
   - Fetches active rows for today from DB via `db.fetch_active_worklist_rows`.
   - Applies routing rules (`routing.should_route_row`).
   - Builds output entries (`payload.build_payload_entries`).
   - Serializes payload, computes hash, checks against `state/last_state.json`.
   - Sends payload when changed and not in dry-run (`sync_client.post_payload`).
3. `main.run_loop` repeats the cycle for poll-loop mode.

## Windows tray mode

- `tray.py` starts a background poll thread and a pystray icon/message loop.
- Tray menu shows:
  - Status (`Running`, `Dry-run`, `Error`)
  - Last poll time
  - Last POST result
  - Today's routed count
  - Open today's history
  - Poll once now
  - Toggle dry-run
  - Exit
- Tray callbacks call into the shared `main.run_once` function so poll logic stays identical to CLI mode.
- Exit stops the background thread cleanly and closes the tray icon loop.

## Data model and sources

- Database source tables:
  - `public.mwl`
  - `public.h2opd_doct_ord`
- Shared fields used for routing/payload:
  - MWL identifiers: `mwl_key`, `eghis_key`
  - patient identifiers: `patient_id` (required), plus requested/optional metadata
  - order fields: `ord_cd`, modality/department/cancel flags

## Module map

- `main.py`
  - CLI orchestration (`poll-once`, `poll-loop`, `test-post`, `tray`)
  - Poll coordinator (`run_once`, `run_loop`)
  - Loads config and routes to mode handler.
- `db.py`
  - DB configuration and query execution.
- `routing.py`
  - `should_route_row` rule set for `BMD`, `INNOVISION`, and ignored reasons.
- `payload.py`
  - Payload formatting and hash calculation.
- `state.py`
  - Last payload hash persistence for idempotency.
- `history.py`
  - Local JSONL event log writer for today’s events (`state/history-YYYYMMDD.jsonl`).
- `tray.py`
  - Windows tray controller and background polling thread.
- `sync_client.py`
  - Sync endpoint POST client.

## History log contract

- File:
  - `state/history-YYYYMMDD.jsonl`
- One JSON line per event:
  - `poll_started`
  - `poll_completed`
  - `routed_item`
  - `ignored_item`
  - `sync_posted`
  - `sync_failed`
  - `no_change`
- Logged fields include:
  - `timestamp`, `event_type`, `source_key`, `eghis_key`, `patient_id`, `modality`, `route`, `accession_no`, `order_code`, `result`, `status`, optional `reason`.
- No explicit PII like name/phone/chart text is written by default.

## Current known checkpoint

- DB read source remains `public.mwl` joined with `public.h2opd_doct_ord`.
- Routing still depends on:
  - `scheduled_proc_status`
  - `proc_dept_cd`
  - `dc_yn`
  - modality and configured `BMD` order codes.
- Dedup persists `payload_hash` in local state JSON.
- Tray mode is now available and writes daily JSONL history for inspection.

## Maintenance rule

- Update this document when architectural changes occur:
  - new poll modes, routing logic, payload contract changes, DB source/query changes, or history schema changes.
