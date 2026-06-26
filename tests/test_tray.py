import importlib
import json
from pathlib import Path

import pytest

from kaoseghis_pacs import main, tray


def _make_settings(tmp_path, dry_run=False):
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
        routing_path=str(tmp_path / 'order_routing.json'),
        state_path=str(tmp_path / 'state' / 'last_state.json'),
        connect_timeout_seconds=5,
        query_timeout_seconds=3,
    )


def test_tray_mode_is_windows_only(monkeypatch, tmp_path):
    monkeypatch.setattr(tray, '_is_windows_platform', lambda: False)
    with pytest.raises(RuntimeError, match='Windows-only'):
        tray.start_tray(_make_settings(tmp_path))


def test_tray_mode_reports_missing_dependencies(monkeypatch, tmp_path):
    monkeypatch.setattr(tray, '_is_windows_platform', lambda: True)
    monkeypatch.setattr(tray, '_resolve_tray_dependencies', lambda: (None, None, None))
    with pytest.raises(RuntimeError, match='dependencies'):
        tray.start_tray(_make_settings(tmp_path))


def test_parser_accepts_tray_mode():
    parser = main.build_parser()
    args = parser.parse_args(['tray'])
    assert args.mode == 'tray'


def test_tray_module_imports_without_syntax_error():
    importlib.import_module('kaoseghis_pacs.tray')


def test_tray_run_once_uses_compatible_history_writer(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path)
    controller = tray._TrayController(settings, pystray=object(), Image=object(), ImageDraw=object())

    def fake_run_once(settings_arg, fetcher=None, sender=None, history_writer=None):
        assert callable(history_writer)
        history_writer(
            tray._to_history_path(settings_arg),
            event_type='poll_started',
            status='running',
            result='ok',
            source_key='mwl:9001',
            eghis_key='9001_1_0',
            patient_id='1001',
            modality='DR',
            route='INNOVISION',
            accession_no='A-1',
            order_code='XRAY01',
        )
        return {'rows_routed': 4, 'posted_summary': 'ok'}

    monkeypatch.setattr(main, 'run_once', fake_run_once)

    controller._run_once()
    assert controller._todays_routed_count == 4


def test_tray_run_once_writes_history_event(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path)
    controller = tray._TrayController(settings, pystray=object(), Image=object(), ImageDraw=object())
    def fake_run_once(settings_arg, fetcher=None, sender=None, history_writer=None):
        history_writer(
            tray._to_history_path(settings_arg),
            event_type='poll_started',
            result='ok',
            status='running',
            source_key='mwl:9002',
            eghis_key='9002_1_0',
            patient_id='1002',
            modality='DR',
            route='INNOVISION',
            accession_no='A-2',
            order_code='XRAY01',
        )
        return {'rows_routed': 1, 'posted_summary': 'ok'}

    monkeypatch.setattr(main, 'run_once', fake_run_once)

    controller._run_once()

    history_path = Path(tray._to_history_path(settings))
    lines = history_path.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event['event_type'] == 'poll_started'
    assert event['status'] == 'running'


def test_tray_run_once_routed_count_uses_last_poll_value(monkeypatch, tmp_path):
    settings = _make_settings(tmp_path)
    controller = tray._TrayController(settings, pystray=object(), Image=object(), ImageDraw=object())
    values = iter([{'rows_routed': 2, 'posted_summary': 'ok'}, {'rows_routed': 2, 'posted_summary': 'ok'}])

    def fake_run_once(settings_arg, fetcher=None, sender=None, history_writer=None):
        return next(values)

    monkeypatch.setattr(main, 'run_once', fake_run_once)

    controller._run_once()
    assert controller._todays_routed_count == 2
    controller._run_once()
    assert controller._todays_routed_count == 2


def test_load_or_generate_icon_uses_tray_icon_path(tmp_path, monkeypatch):
    Image = pytest.importorskip('PIL.Image')
    ImageDraw = pytest.importorskip('PIL.ImageDraw')
    custom_icon = tmp_path / 'custom-icon.png'
    Image.new('RGB', (16, 16), (255, 0, 0)).save(custom_icon)
    monkeypatch.setenv('TRAY_ICON_PATH', str(custom_icon))
    try:
        icon = tray._load_or_generate_icon(Image, ImageDraw, status='Running')
    finally:
        monkeypatch.delenv('TRAY_ICON_PATH', raising=False)
    assert isinstance(icon, Image.Image)
    assert icon.size == (32, 32)
    assert icon.getpixel((0, 0)) == (255, 0, 0)


def test_load_or_generate_icon_falls_back_to_generated(monkeypatch):
    Image = pytest.importorskip('PIL.Image')
    ImageDraw = pytest.importorskip('PIL.ImageDraw')
    monkeypatch.delenv('TRAY_ICON_PATH', raising=False)
    called = False

    def _fake_generate(_Image, _ImageDraw, status):
        nonlocal called
        called = True
        return 'generated-icon'

    monkeypatch.setattr(tray, '_generate_k_icon', _fake_generate)
    icon = tray._load_or_generate_icon(Image, ImageDraw, status='Running')
    assert called
    assert icon == 'generated-icon'
