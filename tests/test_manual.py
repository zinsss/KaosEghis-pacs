import os
import sys
from datetime import datetime

import pytz

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kaoseghis_pacs import manual, main


def _make_settings(tmp_path, dry_run=True):
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
        routing_path=str(tmp_path / 'routing.json'),
        state_path=str(tmp_path / 'state.json'),
        connect_timeout_seconds=5,
        query_timeout_seconds=3,
    )


def test_manual_payload_builder_xray():
    now = datetime(2026, 6, 26, 10, 11, 22, tzinfo=pytz.timezone('Asia/Seoul'))
    values = {
        'study_type': 'XRAY',
        'patient_id': '7435',
        'patient_name': '이진성',
        'patient_sex': 'M',
        'patient_birth_date': '19830210',
        'procedure_description': '흉부 X선',
        'accession_no': manual._make_acc_no('7435', now),
        'scheduled_date': now.strftime('%Y%m%d'),
        'scheduled_time': now.strftime('%H%M%S'),
    }
    entry = manual.build_manual_payload_entry(values, now=now)
    assert entry['source_key'] == f"manual:INNOVISION:{manual._make_acc_no('7435', now)}"
    assert entry['eghis_key'] == f"manual:{manual._make_acc_no('7435', now)}"
    assert entry['modality'] == 'CR'
    assert entry['station_aet'] == 'INNOVISION'
    assert entry['route'] == 'INNOVISION'
    assert entry['order_code'] == 'MANUAL'


def test_manual_payload_builder_bmd():
    now = datetime(2026, 6, 26, 10, 11, 22, tzinfo=pytz.timezone('Asia/Seoul'))
    values = {
        'study_type': 'BMD',
        'patient_id': '8437',
        'patient_name': '홍길동',
        'patient_sex': 'F',
        'patient_birth_date': '19900101',
        'procedure_description': 'BMD',
        'accession_no': manual._make_acc_no('8437', now),
        'scheduled_date': now.strftime('%Y%m%d'),
        'scheduled_time': now.strftime('%H%M%S'),
    }
    entry = manual.build_manual_payload_entry(values, now=now)
    assert entry['source_key'] == f"manual:BMD:{manual._make_acc_no('8437', now)}"
    assert entry['eghis_key'] == f"manual:{manual._make_acc_no('8437', now)}"
    assert entry['modality'] == 'BMD'
    assert entry['station_aet'] == 'BMD'
    assert entry['route'] == 'BMD'


def test_manual_validation_dob():
    errors = manual.validate_manual_form({
        'study_type': 'XRAY',
        'patient_id': '7435',
        'patient_name': '이진성',
        'patient_sex': 'M',
        'patient_birth_date': '1983021',
        'accession_no': 'MANUAL-20260626-101122-7435',
        'scheduled_date': '20260626',
        'scheduled_time': '101122',
    })
    assert 'Patient DOB must be 8 digits.' in errors


def test_manual_payload_source_key_and_accession_format():
    now = datetime(2026, 6, 26, 10, 11, 22, tzinfo=pytz.timezone('Asia/Seoul'))
    values = {
        'study_type': 'BMD',
        'patient_id': '9001',
        'patient_name': '김철수',
        'patient_sex': 'M',
        'patient_birth_date': '19900101',
        'procedure_description': 'BMD',
        'accession_no': manual._make_acc_no('9001', now),
        'scheduled_date': now.strftime('%Y%m%d'),
        'scheduled_time': now.strftime('%H%M%S'),
    }
    entry = manual.build_manual_payload_entry(values, now=now)
    assert entry['source_key'].startswith('manual:BMD:')
    assert entry['accession_no'] == f"MANUAL-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-9001"
    assert entry['source_key'].endswith(entry['accession_no'])


def test_manual_dry_run_does_not_post(tmp_path):
    settings = _make_settings(tmp_path, dry_run=True)
    posted = {'count': 0}

    def fake_post(*_args, **_kwargs):
        posted['count'] += 1
        raise AssertionError('should not be called in dry-run')

    now = datetime(2026, 6, 26, 10, 11, 22, tzinfo=pytz.timezone('Asia/Seoul'))
    patient_id = '7435'
    result = manual.run_manual_payload(
        settings,
        {
            'study_type': 'XRAY',
            'patient_id': patient_id,
            'patient_name': '이진성',
            'patient_sex': 'M',
            'patient_birth_date': '19830210',
            'procedure_description': '흉부 X선',
            'accession_no': manual._make_acc_no(patient_id, now),
            'scheduled_date': now.strftime('%Y%m%d'),
            'scheduled_time': now.strftime('%H%M%S'),
        },
        now=now,
        sender=fake_post,
    )
    assert result['posted'] is False
    assert result['posted_summary'] == 'dry-run'
    assert posted['count'] == 0
