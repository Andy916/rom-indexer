# ROM Indexer

A local web app for cleaning ROM filenames, sorting games into system folders, and recording metadata in SQLite.

## Windows installer

The Windows installer is built for 64-bit Windows and installs per user without administrator access. It adds a Start Menu shortcut, starts the local app, and opens the browser. Use the ROM Indexer tray icon to exit the app. The server listens only on `127.0.0.1`.

The database, organized ROMs, and mounted-folder input live in `%LOCALAPPDATA%\ROM Indexer`. Uninstalling the app leaves this user data in place.

To build locally on Windows, install Python 3.12 and Inno Setup 6, then run:

```powershell
python -m pip install -r requirements-windows.txt
./packaging/windows/build.ps1
```

The build creates `dist/installer/ROMIndexer-Setup-0.1.0.exe`. GitHub Actions can build the same installer on demand; pushing a `v*` tag builds it and publishes a GitHub Release. The installer does not include a shared TheGamesDB key. To enable metadata, set `THEGAMESDB_API_KEY` in your Windows user environment before launching the app.

## Run with Docker

1. Put ROMs in the `roms/` folder, or select a folder from the browser after starting the app.
2. Run `docker compose up --build` from this directory.
3. Open [http://localhost:8000](http://localhost:8000).
4. Choose **Upload folder** to send files to the local app, or **Mounted folder** to index files already under `roms/`.

The mounted ROM folder is read-only. Organized copies are written to `data/organized/`, the SQLite index is `data/roms.db`, and **Download organized library** creates a ZIP archive.

## TheGamesDB metadata

Metadata lookup is optional. Set `THEGAMESDB_API_KEY` in the environment before starting Compose to enable game matching and cover-art URLs. For example, in PowerShell:

```powershell
$env:THEGAMESDB_API_KEY = "your-api-key"
docker compose up --build
```

```bash
export THEGAMESDB_API_KEY="your-api-key"
docker compose up --build
```

The app sends cleaned game titles to TheGamesDB for lookup. ROM file contents are not sent to the API. Without a key, local cleaning, organization, and SQLite indexing still work.

## Run directly with Python

Requires Python 3.10 or newer.

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

By default, direct runs read mounted-folder input from `roms/` and store the database and organized copies in `data/`. Set `ROM_ROOT`, `DATA_DIR`, `OUTPUT_DIR`, and `DATABASE_PATH` to change those locations.

## Supported systems

System folders are inferred from common extensions including GB, GBC, GBA, NES, SNES, Nintendo DS/3DS/64/Wii, Sega Genesis/Master System/Game Gear, PSP, and common disc-image formats. Unsupported files are skipped. Filenames have region/version tags and common bracketed release labels removed; original extensions are preserved.
# rom-indexer