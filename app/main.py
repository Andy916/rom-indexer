import asyncio
import hashlib
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.cleaner import SYSTEMS, clean_title, detect_system
from app.database import initialize_database, list_roms, rom_count, save_rom
from app.scraper import download_cover, fetch_metadata


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_DIR / "data"))).resolve()
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(DATA_DIR / "organized"))).resolve()
ROM_ROOT = Path(os.getenv("ROM_ROOT", str(PROJECT_DIR / "roms"))).resolve()
API_KEY = os.getenv("THEGAMESDB_API_KEY", "")
MAX_FILES = int(os.getenv("MAX_FILES_PER_BATCH", "1000"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_MB", "8192")) * 1024 * 1024
TEMPLATES = Jinja2Templates(directory=str(PROJECT_DIR / "app" / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	initialize_database()
	yield


app = FastAPI(title="ROM Indexer", lifespan=lifespan)


def _rom_extension(filename: str) -> str | None:
	lowered = filename.lower()
	return next(
		(extension for extension in sorted(SYSTEMS, key=len, reverse=True) if lowered.endswith(extension)),
		None,
	)


def _file_digest(path: Path) -> str:
	digest = hashlib.sha256()
	with path.open("rb") as source:
		for chunk in iter(lambda: source.read(1024 * 1024), b""):
			digest.update(chunk)
	return digest.hexdigest()


def _destination_for(system: str, title: str, extension: str, digest: str) -> Path:
	folder = OUTPUT_DIR / system
	folder.mkdir(parents=True, exist_ok=True)
	destination = folder / f"{title}{extension}"
	if not destination.exists() or _file_digest(destination) == digest:
		return destination
	return folder / f"{title} ({digest[:10]}){extension}"


async def _index_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
	if not sources:
		return []

	semaphore = asyncio.Semaphore(6)
	timeout = httpx.Timeout(15.0, connect=5.0)
	async with httpx.AsyncClient(timeout=timeout) as client:

		async def lookup(source: dict[str, Any]) -> dict[str, Any] | None:
			async with semaphore:
				return await fetch_metadata(source["title"], client, API_KEY)

		metadata = await asyncio.gather(*(lookup(source) for source in sources))

		async def save_cover(game: dict[str, Any] | None) -> str | None:
			if not game or not game.get("cover_url") or not game.get("gamesdb_id"):
				return None
			async with semaphore:
				try:
					image = await download_cover(game["cover_url"], client)
				except httpx.HTTPError:
					return None
			if not image:
				return None
			content, extension = image
			destination = OUTPUT_DIR / "_covers" / f"{game['gamesdb_id']}{extension}"
			destination.parent.mkdir(parents=True, exist_ok=True)
			await asyncio.to_thread(destination.write_bytes, content)
			return destination.relative_to(DATA_DIR).as_posix()

		cover_paths = await asyncio.gather(*(save_cover(game) for game in metadata))

	results = []
	for source, game, cover_path in zip(sources, metadata, cover_paths):
		path = source["path"]
		digest = await asyncio.to_thread(_file_digest, path)
		extension = source["extension"]
		destination = _destination_for(source["system"], source["title"], extension, digest)
		await asyncio.to_thread(shutil.copy2, path, destination)
		output_path = destination.relative_to(DATA_DIR).as_posix()
		record = {
			"source_name": source["source_name"],
			"clean_title": source["title"],
			"system": source["system"],
			"output_path": output_path,
			"file_size": path.stat().st_size,
			"release_date": game.get("release_date") if game else None,
			"overview": game.get("overview") if game else None,
			"cover_url": game.get("cover_url") if game else None,
			"cover_path": cover_path,
			"gamesdb_id": game.get("gamesdb_id") if game else None,
		}
		save_rom(record)
		results.append(
			{
				**record,
				"matched": game is not None,
				"status": "Metadata found" if game else "Title cleaned",
			}
		)
	return results


@app.get("/")
async def home(request: Request):
	return TEMPLATES.TemplateResponse(
		request=request,
		name="index.html",
		context={"api_configured": bool(API_KEY)},
	)


@app.get("/api/roms")
async def get_roms():
	return {"count": rom_count(), "roms": list_roms()}


@app.get("/api/covers/{filename}")
async def get_cover(filename: str):
	if Path(filename).name != filename or Path(filename).suffix.lower() not in {
		".jpg", ".jpeg", ".png", ".webp"
	}:
		raise HTTPException(status_code=404, detail="Cover not found.")
	cover = OUTPUT_DIR / "_covers" / filename
	if not cover.is_file():
		raise HTTPException(status_code=404, detail="Cover not found.")
	return FileResponse(cover)


@app.post("/api/index-upload")
async def index_upload(files: list[UploadFile] = File(...)):
	if len(files) > MAX_FILES:
		raise HTTPException(status_code=413, detail=f"Choose no more than {MAX_FILES} files.")

	staging = DATA_DIR / ".staging" / uuid.uuid4().hex
	staging.mkdir(parents=True, exist_ok=True)
	sources = []
	try:
		for upload in files:
			filename = (upload.filename or "").replace("\\", "/")
			extension = _rom_extension(filename)
			if not extension:
				continue
			clean_name = PurePosixPath(filename).name
			title = clean_title(clean_name)
			target = staging / f"{uuid.uuid4().hex}{extension}"
			size = 0
			with target.open("wb") as destination:
				while chunk := await upload.read(1024 * 1024):
					size += len(chunk)
					if size > MAX_FILE_BYTES:
						raise HTTPException(
							status_code=413,
							detail=f"{clean_name} exceeds the per-file upload limit.",
						)
					destination.write(chunk)
			sources.append(
				{
					"path": target,
					"source_name": filename,
					"title": title,
					"system": detect_system(clean_name),
					"extension": extension,
				}
			)

		if not sources:
			raise HTTPException(status_code=400, detail="No supported ROM files were selected.")
		results = await _index_sources(sources)
		return {"processed": len(results), "matched": sum(row["matched"] for row in results), "results": results}
	finally:
		for upload in files:
			await upload.close()
		shutil.rmtree(staging, ignore_errors=True)


@app.post("/api/index-folder")
async def index_folder(folder: str = Form("")):
	ROM_ROOT.mkdir(parents=True, exist_ok=True)
	requested = (ROM_ROOT / folder).resolve()
	if not requested.is_relative_to(ROM_ROOT) or not requested.is_dir():
		raise HTTPException(status_code=400, detail="Choose a folder inside the mounted ROM library.")

	paths = sorted(
		path
		for path in requested.rglob("*")
		if path.is_file() and path.resolve().is_relative_to(ROM_ROOT) and _rom_extension(path.name)
	)
	if len(paths) > MAX_FILES:
		raise HTTPException(status_code=413, detail=f"Choose a folder with no more than {MAX_FILES} ROM files.")
	if not paths:
		raise HTTPException(status_code=400, detail="No supported ROM files were found in that folder.")

	sources = []
	for path in paths:
		relative_name = path.relative_to(ROM_ROOT).as_posix()
		extension = _rom_extension(path.name)
		sources.append(
			{
				"path": path,
				"source_name": relative_name,
				"title": clean_title(path.name),
				"system": detect_system(path.name),
				"extension": extension,
			}
		)
	results = await _index_sources(sources)
	return {"processed": len(results), "matched": sum(row["matched"] for row in results), "results": results}


@app.get("/api/download")
async def download_library():
	archive = DATA_DIR / "roms-organized.zip"
	await asyncio.to_thread(
		shutil.make_archive,
		str(archive.with_suffix("")),
		"zip",
		root_dir=OUTPUT_DIR,
	)
	return FileResponse(archive, filename="roms-organized.zip", media_type="application/zip")
