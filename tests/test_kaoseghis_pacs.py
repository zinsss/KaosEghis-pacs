import os
import sys
from datetime import datetime

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kaoseghis_pacs import payload, routing, state, main


def test_eghis_key_parsing():
    assert routing.parse_eghis_key('261864_1_0') == ('261864', '1', '0')


def test_anchor_selection():
    row = {'scheduled_dttm': '', 'imaging_request_dttm': '20260625070000', 'trigger_dttm': '20260625065500'}
    assert payload.pick_anchor_datetime(row) == '20260625070000'


def test_route_bmd_by_modality():
    row = {'scheduled_proc_status': '100', 'proc_dept_cd': 'XRAY', 'dc_yn': 'N', 'scheduled_modality': 'BMD', 'ord_cd': 'ANY'}
    d = routing.should_route_row(row, ['HC342'])
    assert d.route and d.route.route_name == 'BMD'


def test_route_bmd_by_order_code():
    row = {'scheduled_proc_status': '100', 'proc_dept_cd': 'XRAY', 'dc_yn': 'N', 'scheduled_modality': 'DR', 'ord_cd': 'HC342'}
    d = routing.should_route_row(row, ['HC342'])
    assert d.route and d.route.route_name == 'BMD'


def test_route_dr():
    row = {'scheduled_proc_status': '100', 'proc_dept_cd': 'XRAY', 'dc_yn': 'N', 'scheduled_modality': 'DR', 'ord_cd': 'ANY'}
    d = routing.should_route_row(row, ['HC342'])
    assert d.route and d.route.route_name == 'INNOVISION'


def test_ignore_not_active():
    row = {'scheduled_proc_status': '0', 'proc_dept_cd': 'XRAY', 'dc_yn': 'N', 'scheduled_modality': 'DR', 'ord_cd': 'ANY'}
    assert routing.should_route_row(row, ['HC342']).route is None


def test_ignore_cancelled():
    row = {'scheduled_proc_status': '100', 'proc_dept_cd': 'XRAY', 'dc_yn': 'Y', 'scheduled_modality': 'DR', 'ord_cd': 'ANY'}
    assert routing.should_route_row(row, ['HC342']).ignored_reason == 'cancelled'


def test_ignore_non_xray():
    row = {'scheduled_proc_status': '100', 'proc_dept_cd': 'CT', 'dc_yn': 'N', 'scheduled_modality': 'DR', 'ord_cd': 'ANY'}
    assert routing.should_route_row(row, ['HC342']).ignored_reason == 'non-XRAY department'


def test_accession_fallback():
    row = {'eghis_key': '261864_1_0', 'accession_no': ' '}
    assert payload.normalize_accession_no(row) == 'ACC-261864-1-0'


def test_payload_generation_includes_korean():
    row = {
        'mwl_key': 5,
        'eghis_key': '261864_1_0',
        'patient_id': '7435',
        'patient_name': '홍길동',
        'patient_birth_date': '19830210',
        'patient_sex': 'M',
        'scheduled_dttm': '20260625080000',
        'accession_no': '5',
        'ord_cd': 'HC342',
        'scheduled_proc_desc': 'BMD',
        'requested_proc_desc': 'BMD',
        'route_name': 'BMD',
    }
    rows = payload.build_payload_entries([row], {'BMD': {'modality': 'BMD', 'station_aet': 'BMD', 'description': 'BMD'}, 'DR': {'modality': 'CR', 'station_aet': 'INNOVISION', 'description': 'X-RAY'}}, 'Asia/Seoul')
    assert len(rows) == 1
    assert rows[0]['patient_name'] == '홍길동'
    assert rows[0]['source_key'] == 'mwl:5'


def test_payload_hash_dedup():
    p1 = payload.build_payload([{'a': 1}], datetime.now().isoformat())
    p2 = payload.build_payload([{'a': 1}], datetime.now().isoformat())
    assert payload.payload_hash(p1) == payload.payload_hash(p2)


def make_test_settings(tmp_path, dry_run=False):
    routing_path = tmp_path / 'order_routing.json'
    routing_path.write_text('{"bmd_order_codes":["HC342"],"routes":{"BMD":{"modality":"BMD","station_aet":"BMD","description":"BMD"},"DR":{"modality":"CR","station_aet":"INNOVISION","description":"X-RAY"}}}', encoding='utf-8')
    return main.RunSettings(
        db_host='127.0.0.1',
        db_port=5432,
        db_name='postgres',
        db_user='postgres',
        db_password='x',
        sync_url='http://localhost:1',
        poll_interval_seconds=10,
        timezone='Asia/Seoul',
        dry_run=dry_run,
        routing_path=str(routing_path),
        state_path=str(tmp_path / 'state.json'),
        connect_timeout_seconds=5,
        query_timeout_seconds=3,
    )


def test_dry_run_does_not_post(monkeypatch, tmp_path):
    called = {'count': 0}
    def fake_fetcher(cfg, today):
        return [
            {
                'mwl_key': 1,
                'eghis_key': '1_1_1',
                'patient_id': 'P1',
                'patient_name': '김철수',
                'patient_birth_date': '19900101',
                'patient_sex': 'M',
                'scheduled_dttm': '20260625080000',
                'anchor_dttm': '20260625080000',
                'accession_no': '10',
                'ord_cd': 'HC342',
                'scheduled_proc_desc': 'BMD',
                'requested_proc_desc': 'BMD',
                'proc_dept_cd': 'XRAY',
                'dc_yn': 'N',
                'scheduled_modality': 'BMD',
            }
        ]

    def fake_post(*args, **kwargs):
        called['count'] += 1
        return True

    cfg = make_test_settings(tmp_path, dry_run=True)
    monkeypatch.setattr(main, 'payload', payload)
    result = main.run_once(cfg, fetcher=fake_fetcher, sender=fake_post)
    assert result['posted'] is False
    assert result['posted_summary'] == 'dry-run'
    assert called['count'] == 0


def test_failed_post_does_not_crash(monkeypatch, tmp_path):
    def fake_fetcher(cfg, today):
        return [
            {
                'mwl_key': 1,
                'eghis_key': '1_1_1',
                'patient_id': 'P1',
                'patient_name': '김철수',
                'patient_birth_date': '19900101',
                'patient_sex': 'M',
                'scheduled_dttm': '20260625080000',
                'anchor_dttm': '20260625080000',
                'accession_no': '10',
                'ord_cd': 'HC342',
                'scheduled_proc_desc': 'BMD',
                'requested_proc_desc': 'BMD',
                'proc_dept_cd': 'XRAY',
                'dc_yn': 'N',
                'scheduled_modality': 'BMD',
            }
        ]

    class Boom:
        def __call__(self, *_args, **_kwargs):
            raise RuntimeError('network down')

    cfg = make_test_settings(tmp_path, dry_run=False)
    with pytest.raises(RuntimeError):
        main.run_once(cfg, fetcher=fake_fetcher, sender=Boom())


