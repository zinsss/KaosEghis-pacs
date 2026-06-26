from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import pytz

from . import history

if TYPE_CHECKING:
    from .main import RunSettings


def _is_windows_platform() -> bool:
    return os.name == 'nt'


def _resolve_tray_dependencies():
    try:
        import pystray
        from PIL import Image, ImageDraw
        return pystray, Image, ImageDraw
    except Exception:
        return None, None, None


def start_tray(settings: 'RunSettings') -> None:
    if not _is_windows_platform():
        raise RuntimeError('tray mode is Windows-only')
    pystray, Image, ImageDraw = _resolve_tray_dependencies()
    if pystray is None or Image is None or ImageDraw is None:
        raise RuntimeError('tray mode requires optional dependencies: pystray, Pillow')
    controller = _TrayController(settings, pystray=pystray, Image=Image, ImageDraw=ImageDraw)
    controller.run()


def _to_history_path(settings: 'RunSettings') -> str:
    return history.history_file_for_today(settings.state_path, settings.timezone)


class _TrayController:
    def __init__(
        self,
        settings: 'RunSettings',
        pystray: Any,
        Image: Any,
        ImageDraw: Any,
    ):
        self._settings = settings
        self._pystray = pystray
        self._Image = Image
        self._ImageDraw = ImageDraw
        self._dry_run = bool(settings.dry_run)
        self._status = 'Dry-run' if self._dry_run else 'Running'
        self._last_poll_time = '-'
        self._last_post_result = '-'
        self._todays_routed_count = 0
        self._stop_requested = threading.Event()
        self._poll_lock = threading.Lock()
        self._icon = None
        self._poll_thread: threading.Thread | None = None

    def run(self) -> None:
        menu = self._build_menu()
        self._icon = self._pystray.Icon(
            name='kaoseghis-pacs',
            title='Kaoseghis PACS',
            icon=self._build_icon_image(),
            menu=menu,
        )
        self._poll_thread = threading.Thread(target=self._poll_loop, name='kaoseghis-pacs-tray-poll', daemon=True)
        self._poll_thread.start()
        self._icon.run()
        self._stop_requested.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=5)

    def _build_icon_image(self):
        if self._status == 'Error':
            fill = (196, 0, 0)
        elif self._status == 'Dry-run':
            fill = (255, 165, 0)
        else:
            fill = (0, 128, 0)
        image = self._Image.new('RGB', (32, 32), 'white')
        draw = self._ImageDraw.Draw(image)
        draw.ellipse((4, 4, 28, 28), fill=fill, outline='black')
        return image

    def _format_timestamp(self) -> str:
        return datetime.now(pytz.timezone(self._settings.timezone)).strftime('%Y-%m-%d %H:%M:%S')

    def _build_menu(self):
        return self._pystray.Menu(
            self._pystray.MenuItem(f'Status: {self._status}', lambda *_: None, enabled=False),
            self._pystray.MenuItem(f'Last poll: {self._last_poll_time}', lambda *_: None, enabled=False),
            self._pystray.MenuItem(f'Last POST result: {self._last_post_result}', lambda *_: None, enabled=False),
            self._pystray.MenuItem(f'Last routed count: {self._todays_routed_count}', lambda *_: None, enabled=False),
            self._pystray.MenuItem("Open today's history", self._open_history),
            self._pystray.MenuItem('Poll once now', self._poll_once),
            self._pystray.MenuItem(
                'Dry-run mode',
                self._toggle_dry_run,
                checked=lambda *_: self._dry_run,
            ),
            self._pystray.MenuItem('Exit', self._exit),
        )

    def _refresh_menu(self):
        if self._icon is None:
            return
        self._icon.menu = self._build_menu()
        self._icon.update_menu()
        self._icon.icon = self._build_icon_image()

    def _history_path(self) -> str:
        return _to_history_path(self._settings)

    def _record_history(self, history_path: str, event_type: str, **fields: str) -> None:
        history.append_event(history_path, event_type, **fields)

    def _run_once(self) -> None:
        if not self._poll_lock.acquire(blocking=False):
            return
        try:
            from . import main
            current_settings = replace(self._settings, dry_run=self._dry_run)
            result = main.run_once(
                current_settings,
                history_writer=self._record_history,
            )
            if result.get('posted_summary', '') == 'dry-run':
                self._status = 'Dry-run'
            elif self._status != 'Error':
                self._status = 'Running'
            self._last_poll_time = self._format_timestamp()
            self._last_post_result = result.get('posted_summary', '-')
            self._todays_routed_count = int(result.get('rows_routed', 0))
        except Exception as exc:
            self._status = 'Error'
            self._last_post_result = f'poll_failed: {exc}'
            self._record_history(self._history_path(), 'poll_failed', status='failed', result='failed', reason=str(exc))
        finally:
            self._poll_lock.release()
            self._refresh_menu()

    def _poll_loop(self):
        while not self._stop_requested.is_set():
            self._run_once()
            if self._stop_requested.wait(self._settings.poll_interval_seconds):
                break

    def _poll_once(self, _icon=None, _item=None):
        threading.Thread(target=self._run_once, daemon=True, name='kaoseghis-pacs-tray-single-poll').start()

    def _toggle_dry_run(self, _icon=None, _item=None):
        self._dry_run = not self._dry_run
        if self._status != 'Error':
            self._status = 'Dry-run' if self._dry_run else 'Running'
        self._refresh_menu()

    def _open_history(self, _icon=None, _item=None):
        path = Path(self._history_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        try:
            subprocess.Popen(['notepad.exe', str(path)], shell=False)
        except OSError:
            os.startfile(str(path))

    def _exit(self, icon, _item=None):
        self._stop_requested.set()
        self._status = 'Stopping'
        self._refresh_menu()
        icon.stop()
