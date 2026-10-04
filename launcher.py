import ctypes
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import pystray
import uvicorn
from PIL import Image, ImageDraw


APP_NAME = "ROM Indexer"
MUTEX_NAME = "Local\\ROMIndexerDesktop"


def _application_data_dir() -> Path:
	base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
	return base / "ROM Indexer"


def _available_port() -> int:
	with socket.socket() as candidate:
		try:
			candidate.bind(("127.0.0.1", 8765))
			return 8765
		except OSError:
			candidate.bind(("127.0.0.1", 0))
			return candidate.getsockname()[1]


def _open_browser(url: str) -> bool:
	shell_execute = ctypes.windll.shell32.ShellExecuteW
	shell_execute.argtypes = (
		ctypes.c_void_p,
		ctypes.c_wchar_p,
		ctypes.c_wchar_p,
		ctypes.c_wchar_p,
		ctypes.c_wchar_p,
		ctypes.c_int,
	)
	shell_execute.restype = ctypes.c_void_p
	result = shell_execute(None, "open", url, None, None, 1)
	if result and result > 32:
		return True
	if webbrowser.open(url, new=2):
		return True
	ctypes.windll.user32.MessageBoxW(
		None,
		"ROM Indexer is running, but the browser could not be opened.",
		APP_NAME,
		0x10,
	)
	return False


def _tray_image() -> Image.Image:
	image = Image.new("RGB", (64, 64), "#202722")
	draw = ImageDraw.Draw(image)
	draw.rounded_rectangle((13, 16, 51, 48), radius=4, fill="#b9e3a2")
	draw.rectangle((20, 11, 32, 17), fill="#b9e3a2")
	draw.rectangle((21, 24, 43, 27), fill="#202722")
	draw.rectangle((21, 32, 38, 35), fill="#202722")
	return image


def main() -> None:
	mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
	if ctypes.windll.kernel32.GetLastError() == 183:
		ctypes.windll.kernel32.CloseHandle(mutex)
		return

	data_dir = _application_data_dir()
	output_dir = data_dir / "organized"
	rom_root = data_dir / "roms"
	for directory in (data_dir, output_dir, rom_root):
		directory.mkdir(parents=True, exist_ok=True)

	os.environ["DATA_DIR"] = str(data_dir)
	os.environ["DATABASE_PATH"] = str(data_dir / "roms.db")
	os.environ["OUTPUT_DIR"] = str(output_dir)
	os.environ["ROM_ROOT"] = str(rom_root)

	from app.main import app

	port = _available_port()
	url = f"http://127.0.0.1:{port}"
	server = uvicorn.Server(
		uvicorn.Config(
			app,
			host="127.0.0.1",
			port=port,
			log_config=None,
			access_log=False,
		)
	)
	server_thread = threading.Thread(target=server.run, daemon=True)
	server_thread.start()

	deadline = time.monotonic() + 30
	while time.monotonic() < deadline and server_thread.is_alive():
		try:
			with urllib.request.urlopen(f"{url}/api/roms", timeout=1):
				break
		except (OSError, urllib.error.URLError):
			time.sleep(0.2)
	else:
		ctypes.windll.user32.MessageBoxW(
			None,
			"ROM Indexer could not start. Check the application log and try again.",
			APP_NAME,
			0x10,
		)
		return

	_open_browser(url)
	icon = pystray.Icon(
		APP_NAME,
		_tray_image(),
		APP_NAME,
		pystray.Menu(
			pystray.MenuItem(
				"Open ROM Indexer",
				lambda _icon, _item: _open_browser(url),
				default=True,
			),
			pystray.MenuItem("Exit", lambda _icon, _item: _stop(icon, server)),
		),
	)
	icon.run()
	server.should_exit = True
	server_thread.join(timeout=10)
	ctypes.windll.kernel32.CloseHandle(mutex)


def _stop(icon: pystray.Icon, server: uvicorn.Server) -> None:
	server.should_exit = True
	icon.stop()


if __name__ == "__main__":
	main()