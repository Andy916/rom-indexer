from difflib import SequenceMatcher
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


API_BASE = "https://api.thegamesdb.net/v1"


async def fetch_metadata(
	title: str,
	client: httpx.AsyncClient,
	api_key: str,
) -> dict[str, Any] | None:
	"""Fetch a likely TheGamesDB match without making indexing depend on it."""
	if not api_key:
		return None

	try:
		response = await client.get(
			f"{API_BASE}/Games/ByGameName",
			params={
				"apikey": api_key,
				"name": title,
				"fields": "overview",
			},
		)
		response.raise_for_status()
		games = response.json().get("data", {}).get("games", [])
		if not games:
			return None

		best_match = max(
			games,
			key=lambda game: SequenceMatcher(
				None, title.casefold(), game.get("game_title", "").casefold()
			).ratio(),
		)
		similarity = SequenceMatcher(
			None, title.casefold(), best_match.get("game_title", "").casefold()
		).ratio()
		if similarity < 0.55:
			return None

		try:
			cover_url = await _fetch_cover_url(best_match["id"], client, api_key)
		except (httpx.HTTPError, KeyError, TypeError, ValueError):
			cover_url = None
		return {
			"gamesdb_id": best_match.get("id"),
			"release_date": best_match.get("release_date"),
			"overview": best_match.get("overview"),
			"cover_url": cover_url,
		}
	except (httpx.HTTPError, KeyError, TypeError, ValueError):
		return None


async def _fetch_cover_url(
	game_id: int,
	client: httpx.AsyncClient,
	api_key: str,
) -> str | None:
	response = await client.get(
		f"{API_BASE}/Games/Images",
		params={"apikey": api_key, "games_id": game_id},
	)
	response.raise_for_status()
	data = response.json().get("data", {})
	base_url = data.get("base_url", {}).get("original")
	images = data.get("images", {}).get(str(game_id), [])
	if not base_url:
		return None

	boxarts = [image for image in images if image.get("type") == "boxart"]
	front_cover = next(
		(image for image in boxarts if image.get("side") == "front"),
		boxarts[0] if boxarts else None,
	)
	if not front_cover or not front_cover.get("filename"):
		return None
	return urljoin(base_url.rstrip("/") + "/", front_cover["filename"].lstrip("/"))


async def download_cover(
	url: str,
	client: httpx.AsyncClient,
) -> tuple[bytes, str] | None:
	parsed = urlparse(url)
	if parsed.scheme != "https" or not (
		parsed.hostname == "thegamesdb.net"
		or (parsed.hostname and parsed.hostname.endswith(".thegamesdb.net"))
	):
		return None

	response = await client.get(url)
	response.raise_for_status()
	if len(response.content) > 12 * 1024 * 1024:
		return None

	extension = PurePosixPath(parsed.path).suffix.lower()
	if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
		return None
	return response.content, extension
