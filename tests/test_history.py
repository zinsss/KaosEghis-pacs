import json
from pathlib import Path

from kaoseghis_pacs import history


def test_history_file_appends_jsonl_events(tmp_path):
    history_path = tmp_path / 'state' / 'history-20260626.jsonl'
    history.append_event(
        str(history_path),
        event_type='routed_item',
        source_key='mwl:9001',
        eghis_key='9001_1_0',
        patient_id='1001',
        modality='DR',
        route='INNOVISION',
        accession_no='A-1',
        order_code='XRAY01',
        result='routed',
        status='success',
        reason='ok',
        custom='value',
    )

    events = [json.loads(line) for line in history_path.read_text(encoding='utf-8').splitlines()]
    assert len(events) == 1

    event = events[0]
    assert event['event_type'] == 'routed_item'
    assert event['source_key'] == 'mwl:9001'
    assert event['eghis_key'] == '9001_1_0'
    assert event['patient_id'] == '1001'
    assert event['modality'] == 'DR'
    assert event['route'] == 'INNOVISION'
    assert event['accession_no'] == 'A-1'
    assert event['order_code'] == 'XRAY01'
    assert event['result'] == 'routed'
    assert event['status'] == 'success'
    assert event['reason'] == 'ok'
    assert event['custom'] == 'value'


def test_history_does_not_include_forbidden_pii_keys(tmp_path):
    history_path = tmp_path / 'state' / 'history-20260626.jsonl'
    history.append_event(
        str(history_path),
        event_type='ignored_item',
        source_key='mwl:9002',
        eghis_key='9002_1_0',
        patient_id='1002',
        modality='BMD',
        route='BMD',
        accession_no='A-2',
        order_code='HC342',
        result='ignored',
        status='ignored',
        patient_name='홍길동',
        phone='010-1111-2222',
        chart='민감한 텍스트',
    )

    event = json.loads(history_path.read_text(encoding='utf-8').splitlines()[0])
    assert 'patient_name' not in event
    assert 'phone' not in event
    assert 'chart' not in event


def test_history_file_for_today_uses_state_dir(tmp_path):
    state_path = Path(tmp_path) / 'state' / 'last_state.json'
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{\"payload_hash\": \"x\"}', encoding='utf-8')

    path = history.history_file_for_today(str(state_path), 'Asia/Seoul')
    assert Path(path).name.startswith('history-')
    assert str(Path(path).parent) == str(state_path.parent)
