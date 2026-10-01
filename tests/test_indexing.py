import io
import tempfile
import unittest
import zipfile
import httpx
from pathlib import Path
from unittest.mock import patch

from app import database, main
from app.scraper import download_cover, fetch_metadata


class IndexingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.data_dir = self.root / "data"
        self.output_dir = self.data_dir / "organized"
        self.rom_root = self.root / "roms"
        self.database_patch = patch.object(database, "DATABASE_PATH", self.data_dir / "roms.db")
        self.data_patch = patch.object(main, "DATA_DIR", self.data_dir)
        self.output_patch = patch.object(main, "OUTPUT_DIR", self.output_dir)
        self.rom_patch = patch.object(main, "ROM_ROOT", self.rom_root)
        self.key_patch = patch.object(main, "API_KEY", "")
        for active_patch in (
            self.database_patch,
            self.data_patch,
            self.output_patch,
            self.rom_patch,
            self.key_patch,
        ):
            active_patch.start()
        self.lifespan_context = main.app.router.lifespan_context(main.app)
        await self.lifespan_context.__aenter__()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan_context.__aexit__(None, None, None)
        for active_patch in (
            self.database_patch,
            self.data_patch,
            self.output_patch,
            self.rom_patch,
            self.key_patch,
        ):
            active_patch.stop()
        self.temporary_directory.cleanup()

    async def test_upload_indexes_and_downloads_organized_library(self):
        response = await self.client.post(
            "/api/index-upload",
            files=[
                (
                    "files",
                    ("library/Metroid Fusion (USA) [!].gba", b"rom bytes", "application/octet-stream"),
                )
            ],
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["clean_title"], "Metroid Fusion")
        self.assertEqual(result["system"], "Nintendo Game Boy Advance")
        self.assertFalse(result["matched"])
        organized_file = self.output_dir / "Nintendo Game Boy Advance" / "Metroid Fusion.gba"
        self.assertEqual(organized_file.read_bytes(), b"rom bytes")
        self.assertEqual(database.rom_count(), 1)

        archive = await self.client.get("/api/download")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
            self.assertIn("Nintendo Game Boy Advance/Metroid Fusion.gba", zipped.namelist())

    async def test_mounted_folder_indexes_recursively_and_rejects_escape(self):
        source = self.rom_root / "handheld" / "Sonic_2_(Europe).md"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"game data")

        response = await self.client.post("/api/index-folder", data={"folder": "handheld"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["clean_title"], "Sonic 2")
        self.assertTrue((self.output_dir / "Sega Genesis" / "Sonic 2.md").is_file())

        escaped = await self.client.post("/api/index-folder", data={"folder": "../outside"})
        self.assertEqual(escaped.status_code, 400)


class MetadataLookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_gamesdb_lookup_and_cover_download(self):
        def respond(request):
            if request.url.path.endswith("/Games/ByGameName"):
                self.assertEqual(request.url.params["name"], "Metroid Fusion")
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "games": [
                                {
                                    "id": 123,
                                    "game_title": "Metroid Fusion",
                                    "release_date": "2002-11-17",
                                    "overview": "A space adventure.",
                                }
                            ]
                        }
                    },
                )
            if request.url.path.endswith("/Games/Images"):
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "base_url": {"original": "https://cdn.thegamesdb.net/images/original/"},
                            "images": {
                                "123": [
                                    {
                                        "type": "boxart",
                                        "side": "front",
                                        "filename": "boxart/front/123.jpg",
                                    }
                                ]
                            },
                        }
                    },
                )
            if request.url.host == "cdn.thegamesdb.net":
                return httpx.Response(200, content=b"image-bytes")
            return httpx.Response(404)

        transport = httpx.MockTransport(respond)
        async with httpx.AsyncClient(transport=transport) as client:
            game = await fetch_metadata("Metroid Fusion", client, "test-key")
            self.assertEqual(game["gamesdb_id"], 123)
            self.assertEqual(game["release_date"], "2002-11-17")
            image = await download_cover(game["cover_url"], client)

        self.assertEqual(image, (b"image-bytes", ".jpg"))


if __name__ == "__main__":
    unittest.main()