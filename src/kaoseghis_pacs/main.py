from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List

import os
import time
import pytz
from dotenv import load_dotenv

from . import db, payload, routing, state, sync_client

LOGGER = logging.getLogger('kaoseghis-pacs')


@dataclass(frozen=True)
class RunSettings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    sync_url: str
    poll_interval_seconds: int
    timezone: str
    dry_run: bool
    routing_path: str
    state_path: str
    connect_timeout_seconds: int
    query_timeout_seconds: int


def _env_or(value: str, default: str) -> str:
    return value if value not in (None, '') else default


def read_settings_from_env(cli_args: argparse.Namespace) -> RunSettings:
    return RunSettings(
        db_host=_env_or(cli_args.eghis_db_host, os.getenv('EGHIS_DB_HOST', '127.0.0.1')),
        db_port=int(_env_or(cli_args.eghis_db_port, os.getenv('EGHIS_DB_PORT', '5432'))),
        db_name=_env_or(cli_args.eghis_db_name, os.getenv('EGHIS_DB_NAME', 'postgres')),
        db_user=_env_or(cli_args.eghis_db_user, os.getenv('EGHIS_DB_USER', 'postgres')),
        db_password=_env_or(cli_args.eghis_db_password, os.getenv('EGHIS_DB_PASSWORD', '')),
        sync_url=_env_or(cli_args.kaos_mwl_sync_url, os.getenv('KAOS_MWL_SYNC_URL', 'http://192.168.0.200:8085/api/worklist/sync')),
        poll_interval_seconds=int(_env_or(cli_args.poll_interval_seconds, os.getenv('POLL_INTERVAL_SECONDS', '15'))),
        timezone=_env_or(cli_args.timezone, os.getenv('TIMEZONE', 'Asia/Seoul')),
        dry_run=cli_args.dry_run or os.getenv('DRY_RUN', 'true').lower() in ('1', 'true', 'yes', 'y'),
        routing_path=_env_or(cli_args.order_routing_path, os.getenv('ORDER_ROUTING_PATH', 'config/order_routing.example.json')),
        state_path=_env_or(cli_args.state_path, os.getenv('STATE_PATH', 'state/last_state.json')),
        connect_timeout_seconds=int(_env_or(cli_args.connect_timeout_seconds, os.getenv('CONNECT_TIMEOUT_SECONDS', '5'))),
        query_timeout_seconds=int(_env_or(cli_args.query_timeout_seconds, os.getenv('QUERY_TIMEOUT_SECONDS', '3'))),
    )


def _load_routes(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg['bmd_order_codes'], cfg['routes']


def run_once(settings: RunSettings, fetcher: Callable[..., List[Dict[str, Any]]] | None = None, sender: Callable[..., sync_client.SyncResult] | None = None):
    today = datetime.now(pytz.timezone(settings.timezone)).strftime('%Y%m%d')
    cfg_db = db.EGhisDbConfig(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connect_timeout=settings.connect_timeout_seconds,
        query_timeout_ms=settings.query_timeout_seconds * 1000,
    )

    fetch_rows = fetcher or db.fetch_active_worklist_rows
    rows = fetch_rows(cfg_db, today)
    bmd_order_codes, route_defs = _load_routes(settings.routing_path)

    routed_rows: List[Dict[str, Any]] = []
    ignored = {
        'inactive status': 0,
        'non-XRAY department': 0,
        'cancelled': 0,
        'unknown modality': 0,
        'missing patient_id': 0,
    }
    rows_ignored = 0

    route_rows = []
    for row in rows:
        if not (row.get('patient_id') or '').strip():
            rows_ignored += 1
            ignored['missing patient_id'] += 1
            continue

        decision = routing.should_route_row(row, bmd_order_codes)
        if decision.route is None:
            rows_ignored += 1
            reason = decision.ignored_reason or 'unknown'
            ignored[reason] = ignored.get(reason, 0) + 1
            LOGGER.info('Ignore reason=%s source_key=%s', reason, row.get('mwl_key'))
            continue

        out = dict(row)
        out['route_name'] = decision.route.route_name
        route_rows.append(out)
        LOGGER.info(
            'Routed source_key=%s patient_id=%s scheduled_modality=%s order_code=%s route=%s accession_no=%s',
            f"mwl:{row.get('mwl_key')}",
            row.get('patient_id'),
            row.get('scheduled_modality'),
            row.get('ord_cd'),
            decision.route.route_name,
            row.get('accession_no') or '',
        )

    if route_rows:
        route_map = {
            'BMD': route_defs['BMD'],
            'INNOVISION': route_defs['DR'],
        }
    else:
        route_map = {'BMD': route_defs['BMD'], 'INNOVISION': route_defs['DR']}

    entries = payload.build_payload_entries(route_rows, route_map, settings.timezone)
    body = payload.build_payload(entries, datetime.now(pytz.timezone(settings.timezone)).isoformat())
    p_hash = payload.payload_hash(body)

    summary = {
        'rows_seen': len(rows),
        'rows_routed': len(entries),
        'rows_ignored': rows_ignored,
        'payload_hash': p_hash,
        'posted': False,
        'posted_summary': '',
        'ignored': ignored,
    }

    LOGGER.info('Poll summary rows_seen=%s rows_routed=%s rows_ignored=%s payload_hash=%s', len(rows), len(entries), rows_ignored, p_hash)

    if settings.dry_run:
        summary['posted_summary'] = 'dry-run'
        LOGGER.info('Dry-run enabled: skipped POST')
        return summary

    if not entries:
        summary['posted_summary'] = 'empty'
        return summary

    last_state = state.load_state(settings.state_path)
    if last_state.payload_hash == p_hash:
        summary['posted_summary'] = 'no change'
        LOGGER.info('Payload unchanged, skip POST')
        return summary

    do_post = sender or sync_client.post_payload
    result = do_post(settings.sync_url, body, 3)
    summary['posted'] = result.ok
    summary['posted_summary'] = result.summary
    if result.ok:
        state.save_state(settings.state_path, p_hash)
    LOGGER.info('POST result ok=%s status=%s summary=%s', result.ok, result.status_code, result.summary)
    return summary


def run_loop(settings: RunSettings):
    while True:
        try:
            run_once(settings)
        except Exception:
            LOGGER.exception('poll loop iteration failed')
        time.sleep(settings.poll_interval_seconds)


def run_test_post(settings: RunSettings):
    if settings.dry_run:
        LOGGER.info('Dry-run enabled, skipping test-post')
        return {'posted': False, 'posted_summary': 'dry-run'}
    body = payload.sample_payload(settings.timezone)
    result = sync_client.post_payload(settings.sync_url, body, 3)
    LOGGER.info('test-post result ok=%s status=%s summary=%s', result.ok, result.status_code, result.summary)
    return {'posted': result.ok, 'posted_summary': result.summary}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='kaoseghis-pacs agent')
    p.add_argument('mode', choices=['poll-once', 'poll-loop', 'test-post'])
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--eghis-db-host', dest='eghis_db_host', default='')
    p.add_argument('--eghis-db-port', dest='eghis_db_port', default='')
    p.add_argument('--eghis-db-name', dest='eghis_db_name', default='')
    p.add_argument('--eghis-db-user', dest='eghis_db_user', default='')
    p.add_argument('--eghis-db-password', dest='eghis_db_password', default='')
    p.add_argument('--kaos-mwl-sync-url', dest='kaos_mwl_sync_url', default='')
    p.add_argument('--poll-interval-seconds', dest='poll_interval_seconds', default='')
    p.add_argument('--timezone', dest='timezone', default='')
    p.add_argument('--order-routing-path', dest='order_routing_path', default='')
    p.add_argument('--state-path', dest='state_path', default='')
    p.add_argument('--connect-timeout-seconds', dest='connect_timeout_seconds', default='')
    p.add_argument('--query-timeout-seconds', dest='query_timeout_seconds', default='')
    return p


def main():
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    cfg = read_settings_from_env(args)

    if args.mode == 'poll-once':
        run_once(cfg)
    elif args.mode == 'poll-loop':
        run_loop(cfg)
    elif args.mode == 'test-post':
        run_test_post(cfg)


if __name__ == '__main__':
    main()

