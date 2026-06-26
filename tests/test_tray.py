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
