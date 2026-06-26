import os
import sys
from datetime import datetime

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kaoseghis_pacs import main, payload, routing


def _join_rows_fixture():
    return [
        {
            'mwl_key': 1,
            'eghis_key': '9001_1_0',
            'patient_id': '1001',
            'patient_name': '홍길동',
            'patient_birth_date': '19830210',
            'patient_sex': 'M',
            'scheduled_modality': 'BMD',
            'scheduled_proc_status': '100',
            'scheduled_dttm': '20260625080000',
            'imaging_request_dttm': '20260625080100',
            'trigger_dttm': '',
            'replica_dttm': '',
            'accession_no': '',
            'scheduled_proc_desc': 'BMD 검사',
            'requested_proc_desc': 'BMD 검사',
            'anchor_dttm': '20260625080000',
            'ord_cd': 'HC342',
            'ord_ymd': '20260625',
            'ord_no': '1',
            'ord_seq_no': '0',
            'ord_type': 'R',
            'proc_dept_cd': 'XRAY',
            'dc_yn': 'N',
        },
        {
            'mwl_key': 2,
            'eghis_key': '9002_1_0',
            'patient_id': '1002',
            'patient_name': '김철수',
            'patient_birth_date': '19900101',
            'patient_sex': 'M',
            'scheduled_modality': 'DR',
            'scheduled_proc_status': '100',
            'scheduled_dttm': '20260625080500',
            'imaging_request_dttm': '',
            'trigger_dttm': '20260625080600',
            'replica_dttm': '',
            'accession_no': 'A-2',
            'scheduled_proc_desc': '흉부 DR',
            'requested_proc_desc': '흉부 DR',
            'anchor_dttm': '20260625080500',
            'ord_cd': 'XRAY01',
            'ord_ymd': '20260625',
            'ord_no': '2',
            'ord_seq_no': '0',
            'ord_type': 'R',
            'proc_dept_cd': 'XRAY',
            'dc_yn': 'N',
        },
        {
            'mwl_key': 3,
            'eghis_key': '9003_1_0',
            'patient_id': '1003',
            'patient_name': '이영희',
            'patient_birth_date': '19920303',
            'patient_sex': 'F',
            'scheduled_modality': 'DR',
            'scheduled_proc_status': '0',
            'scheduled_dttm': '20260625081000',
            'imaging_request_dttm': '',
            'trigger_dttm': '',
            'replica_dttm': '',
            'accession_no': 'A-3',
            'scheduled_proc_desc': '비활성',
            'requested_proc_desc': '비활성',
            'anchor_dttm': '20260625081000',
            'ord_cd': 'XRAY01',
            'ord_ymd': '20260625',
            'ord_no': '3',
            'ord_seq_no': '0',
            'ord_type': 'R',
            'proc_dept_cd': 'XRAY',
            'dc_yn': 'N',
        },
        {
            'mwl_key': 4,
            'eghis_key': '9004_1_0',
            'patient_id': '1004',
            'patient_name': '박민수',
            'patient_birth_date': '19850505',
            'patient_sex': 'M',
            'scheduled_modality': 'BMD',
            'scheduled_proc_status': '100',
            'scheduled_dttm': '20260625081500',
            'imaging_request_dttm': '',
            'trigger_dttm': '',
            'replica_dttm': '',
            'accession_no': 'A-4',
            'scheduled_proc_desc': '취소 주문',
            'requested_proc_desc': '취소 주문',
            'anchor_dttm': '20260625081500',
            'ord_cd': 'HC342',
            'ord_ymd': '20260625',
            'ord_no': '4',
            'ord_seq_no': '0',
            'ord_type': 'R',
            'proc_dept_cd': 'XRAY',
            'dc_yn': 'Y',
        },
        {
            'mwl_key': 5,
            'eghis_key': '9005_1_0',
            'patient_id': '1005',
            'patient_name': '오세훈',
            'patient_birth_date': '19770707',
            'patient_sex': 'M',
            'scheduled_modality': 'US',
            'scheduled_proc_status': '100',
            'scheduled_dttm': '20260625082000',
            'imaging_request_dttm': '',
            'trigger_dttm': '',
            'replica_dttm': '',
            'accession_no': 'A-5',
            'scheduled_proc_desc': '초음파',
            'requested_proc_desc': '초음파',
            'anchor_dttm': '20260625082000',
            'ord_cd': 'US01',
            'ord_ymd': '20260625',
            'ord_no': '5',
            'ord_seq_no': '0',
            'ord_type': 'R',
            'proc_dept_cd': 'US',
            'dc_yn': 'N',
        },
    ]


def make_settings(tmp_path, dry_run=False, state_content=None):
    routing_path = tmp_path / 'order_routing.json'
    routing_path.write_text(
        '{"bmd_order_codes":["HC342"],"routes":{'
        '"BMD":{"modality":"BMD","station_aet":"BMD","description":"BMD"},'
        '"DR":{"modality":"CR","station_aet":"INNOVISION","description":"X-RAY"}}}'
        ,
        encoding='utf-8',
    )
    state_path = tmp_path / 'state.json'
    if state_content is not None:
        state_path.write_text(state_content, encoding='utf-8')

    return main.RunSettings(
        db_host='127.0.0.1',
        db_port=5432,
        db_name='postgres',
        db_user='postgres',
        db_password='local-pass',
        sync_url='http://127.0.0.1:8085/api/worklist/sync',
        poll_interval_seconds=15,
        timezone='Asia/Seoul',
        dry_run=dry_run,
        routing_path=str(routing_path),
        state_path=str(state_path),
        connect_timeout_seconds=5,
        query_timeout_seconds=3,
    )


def test_eghis_key_parsing():
    assert routing.parse_eghis_key('261864_1_0') == ('261864', '1', '0')


def test_anchor_dttm_selection_priority():
    row = {
        'anchor_dttm': '20260625113000',
        'scheduled_dttm': '20260625112000',
        'imaging_request_dttm': '20260625112900',
        'trigger_dttm': '20260625112800',
        'replica_dttm': '20260625112700',
    }
    assert payload.pick_anchor_datetime(row) == '20260625113000'


def test_routing_bmd_by_scheduled_modality():
    row = {
        'scheduled_proc_status': '100',
        'proc_dept_cd': 'XRAY',
        'dc_yn': 'N',
        'scheduled_modality': 'BMD',
        'ord_cd': 'ANY',
    }
    result = routing.should_route_row(row, ['HC342'])
    assert result.ignored_reason is None
    assert result.route is not None
    assert result.route.route_name == 'BMD'


def test_routing_bmd_by_bmd_order_codes():
    row = {
        'scheduled_proc_status': '100',
        'proc_dept_cd': 'XRAY',
        'dc_yn': 'N',
        'scheduled_modality': 'DR',
        'ord_cd': 'HC342',
    }
    result = routing.should_route_row(row, ['HC342'])
    assert result.route is not None
    assert result.route.route_name == 'BMD'


def test_routing_dr_to_innovation_cr():
    row = {
        'scheduled_proc_status': '100',
        'proc_dept_cd': 'XRAY',
        'dc_yn': 'N',
        'scheduled_modality': 'DR',
        'ord_cd': 'OTHER',
    }
    result = routing.should_route_row(row, ['HC342'])
    assert result.route is not None
    assert result.route.route_name == 'INNOVISION'
    assert result.route.modality == 'CR'
    assert result.route.station_aet == 'INNOVISION'


def test_ignoring_status_not_100():
    row = {
        'scheduled_proc_status': '0',
        'proc_dept_cd': 'XRAY',
        'dc_yn': 'N',
        'scheduled_modality': 'DR',
        'ord_cd': 'ANY',
    }
    result = routing.should_route_row(row, ['HC342'])
    assert result.route is None
    assert result.ignored_reason == 'inactive status'


def test_ignoring_cancelled_order():
    row = {
        'scheduled_proc_status': '100',
        'proc_dept_cd': 'XRAY',
        'dc_yn': 'Y',
        'scheduled_modality': 'DR',
        'ord_cd': 'ANY',
    }
    result = routing.should_route_row(row, ['HC342'])
    assert result.route is None
    assert result.ignored_reason == 'cancelled'


def test_ignoring_non_xray_department():
    row = {
        'scheduled_proc_status': '100',
        'proc_dept_cd': 'CT',
        'dc_yn': 'N',
        'scheduled_modality': 'DR',
        'ord_cd': 'ANY',
    }
    result = routing.should_route_row(row, ['HC342'])
    assert result.route is None
    assert result.ignored_reason == 'non-XRAY department'


def test_accession_fallback_from_eghis_key():
    row = {'eghis_key': '261864_1_0', 'accession_no': ''}
    assert payload.normalize_accession_no(row) == 'ACC-261864-1-0'


def test_payload_generation_shape_for_kaos_mwl():
    row = {
        'mwl_key': 5,
        'eghis_key': '261864_1_0',
        'patient_id': '7435',
        'patient_name': '홍길동',
        'patient_birth_date': '19830210',
        'patient_sex': 'M',
        'scheduled_dttm': '20260625080000',
        'anchor_dttm': '20260625080000',
        'accession_no': '5',
        'ord_cd': 'HC342',
        'route_name': 'BMD',
        'scheduled_proc_desc': 'BMD',
        'requested_proc_desc': 'BMD',
    }
    entries = payload.build_payload_entries(
        [row],
        {'BMD': {'modality': 'BMD', 'station_aet': 'BMD', 'description': 'BMD'}, 'INNOVISION': {'modality': 'CR', 'station_aet': 'INNOVISION', 'description': 'X-RAY'}},
        'Asia/Seoul',
    )
    payload_obj = payload.build_payload(entries, datetime(2026, 6, 25, 8, 0, 0, tzinfo=pytz.timezone('Asia/Seoul')).isoformat())

    assert payload_obj['source'] == 'kaoseghis-pacs'
    assert payload_obj['generated_at']
    assert len(payload_obj['entries']) == 1

    entry = payload_obj['entries'][0]
    assert set(entry.keys()) == {
        'source_key',
        'eghis_key',
        'patient_id',
        'patient_name',
        'patient_birth_date',
        'patient_sex',
        'accession_no',
        'modality',
        'station_aet',
        'scheduled_procedure_step_description',
        'requested_procedure_description',
        'scheduled_date',
        'scheduled_time',
        'order_code',
        'route',
    }
    assert entry['source_key'] == 'mwl:5'
    assert entry['modality'] == 'BMD'
    assert entry['station_aet'] == 'BMD'
    assert entry['route'] == 'BMD'


def test_payload_hash_dedup():
    now = datetime(2026, 6, 25, 8, 0, 0).isoformat()
    first = payload.build_payload([{'a': 1}], now)
    second = payload.build_payload([{'a': 1}], now)
    third = payload.build_payload([{'a': 2}], now)
    assert payload.payload_hash(first) == payload.payload_hash(second)
    assert payload.payload_hash(first) != payload.payload_hash(third)


def test_utf8_korean_patient_name_preservation():
    row = {
        'mwl_key': 6,
        'eghis_key': '261864_1_2',
        'patient_id': '1006',
        'patient_name': '김나영',
        'patient_birth_date': '19990101',
        'patient_sex': 'F',
        'scheduled_dttm': '20260625083000',
        'accession_no': 'K-6',
        'ord_cd': 'HC342',
        'route_name': 'BMD',
        'scheduled_proc_desc': 'BMD',
        'requested_proc_desc': 'BMD',
    }
    entries = payload.build_payload_entries(
        [row],
        {'BMD': {'modality': 'BMD', 'station_aet': 'BMD', 'description': 'BMD'}, 'INNOVISION': {'modality': 'CR', 'station_aet': 'INNOVISION', 'description': 'X-RAY'}},
        'Asia/Seoul',
    )
    assert entries[0]['patient_name'] == '김나영'
    serialized = payload.payload_hash(payload.build_payload(entries, '2026-06-25T08:30:00+09:00'))
    assert isinstance(serialized, str)


def test_dry_run_does_not_post(monkeypatch, tmp_path):
    settings = make_settings(tmp_path, dry_run=True)
    posted = {'called': False}

    def fake_fetcher(*_args, **_kwargs):
        return _join_rows_fixture()[:2]

    def fake_sender(*_args, **_kwargs):
        posted['called'] = True
        return payload.SyncResult(ok=True, status_code=200, summary='should not be called')

    result = main.run_once(settings, fetcher=fake_fetcher, sender=fake_sender)
    assert result['posted'] is False
    assert result['posted_summary'] == 'dry-run'
    assert posted['called'] is False


def test_failed_post_does_not_crash(monkeypatch, tmp_path):
    settings = make_settings(tmp_path, dry_run=False)

    def fake_fetcher(*_args, **_kwargs):
        return _join_rows_fixture()[:2]

    def failing_sender(*_args, **_kwargs):
        raise RuntimeError('connection refused')

    result = main.run_once(settings, fetcher=fake_fetcher, sender=failing_sender)
    assert result['posted'] is False
    assert 'POST failed' in result['posted_summary']


def test_settings_load_from_env(monkeypatch):
    parser = main.build_parser()
    args = parser.parse_args(['poll-once'])

    monkeypatch.setenv('EGHIS_DB_HOST', '127.0.0.2')
    monkeypatch.setenv('EGHIS_DB_PORT', '6543')
    monkeypatch.setenv('EGHIS_DB_NAME', 'eghis_db')
    monkeypatch.setenv('EGHIS_DB_USER', 'eghis_user')
    monkeypatch.setenv('EGHIS_DB_PASSWORD', 'eghis_password')
    monkeypatch.setenv('KAOS_MWL_SYNC_URL', 'http://192.168.1.10:8085/api/worklist/sync')
    monkeypatch.setenv('POLL_INTERVAL_SECONDS', '20')
    monkeypatch.setenv('TIMEZONE', 'Asia/Seoul')
    monkeypatch.setenv('STATE_PATH', '/tmp/state.json')
    monkeypatch.setenv('ORDER_ROUTING_PATH', 'config/order_routing.example.json')

    cfg = main.read_settings_from_env(args)

    assert cfg.db_host == '127.0.0.2'
    assert cfg.db_port == 6543
    assert cfg.db_name == 'eghis_db'
    assert cfg.db_user == 'eghis_user'
    assert cfg.db_password == 'eghis_password'
    assert cfg.sync_url == 'http://192.168.1.10:8085/api/worklist/sync'
    assert cfg.poll_interval_seconds == 20
    assert cfg.state_path == '/tmp/state.json'


def test_fixture_joins_are_processed_as_expected(tmp_path):
    settings = make_settings(tmp_path, dry_run=False)
    def fake_fetcher(*_args, **_kwargs):
        return _join_rows_fixture()

    posted_payloads = []

    def fake_sender(url, payload_obj, timeout):
        posted_payloads.append((url, payload_obj, timeout))
        class Result:
            ok = True
            status_code = 200
            summary = 'ok'
        return Result()

    result = main.run_once(settings, fetcher=fake_fetcher, sender=fake_sender)

    assert result['rows_seen'] == 5
    assert result['rows_routed'] == 2
    assert result['rows_ignored'] == 3
    assert len(posted_payloads) == 1
    assert posted_payloads[0][1]['entries'][0]['route'] == 'BMD'
    assert posted_payloads[0][1]['entries'][1]['route'] == 'INNOVISION'


def test_payload_dedup_skips_unchanged_payload(tmp_path):
    route_rows = payload.build_payload_entries(
        [
            {
                'mwl_key': 1,
                'eghis_key': '9001_1_0',
                'patient_id': '1001',
                'patient_name': '홍길동',
                'patient_birth_date': '19830210',
                'patient_sex': 'M',
                'ord_cd': 'HC342',
                'scheduled_dttm': '20260625080000',
                'anchor_dttm': '20260625080000',
                'accession_no': '',
                'route_name': 'BMD',
            }
        ],
        {'BMD': {'modality': 'BMD', 'station_aet': 'BMD', 'description': 'BMD'}, 'INNOVISION': {'modality': 'CR', 'station_aet': 'INNOVISION', 'description': 'X-RAY'}},
        'Asia/Seoul',
    )
    existing_payload = payload.build_payload(route_rows, '2026-06-25T08:00:00+09:00')
    existing_hash = payload.payload_hash(existing_payload)

    settings = make_settings(tmp_path, dry_run=False, state_content=f'{"payload_hash": "{existing_hash}"}')
    def fake_fetcher(*_args, **_kwargs):
        return [
            {
                'mwl_key': 1,
                'eghis_key': '9001_1_0',
                'patient_id': '1001',
                'patient_name': '홍길동',
                'patient_birth_date': '19830210',
                'patient_sex': 'M',
                'scheduled_modality': 'BMD',
                'scheduled_proc_status': '100',
                'scheduled_dttm': '20260625080000',
                'imaging_request_dttm': '',
                'trigger_dttm': '',
                'replica_dttm': '',
                'accession_no': '',
                'scheduled_proc_desc': 'BMD',
                'requested_proc_desc': 'BMD',
                'anchor_dttm': '20260625080000',
                'ord_cd': 'HC342',
                'ord_ymd': '20260625',
                'ord_no': '1',
                'ord_seq_no': '0',
                'ord_type': 'R',
                'proc_dept_cd': 'XRAY',
                'dc_yn': 'N',
            }
        ]

    def fake_sender(*_args, **_kwargs):
        return payload.SyncResult(ok=True, status_code=200, summary='called')

    result = main.run_once(settings, fetcher=fake_fetcher, sender=fake_sender)
    assert result['posted'] is False
    assert result['posted_summary'] == 'no change'
