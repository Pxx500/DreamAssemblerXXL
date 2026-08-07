import asyncio
import json
from pathlib import Path

import httpx

from daxxl.fullpack_release import ReleaseAsset, expired_translation_asset_ids, publish_fullpack_manifest


class FakeRelease:
    def __init__(self, assets: list[ReleaseAsset] | None = None, failing_upload: str | None = None) -> None:
        self._assets = assets or []
        self.failing_upload = failing_upload
        self.events: list[tuple[str, str]] = []
        self.uploaded_manifest: dict[str, object] | None = None

    def ensure_exists(self) -> None:
        self.events.append(("ensure", ""))

    def assets(self) -> list[ReleaseAsset]:
        return list(self._assets)

    def upload(self, path: Path, *, clobber: bool = False) -> None:
        self.events.append(("upload", path.name))
        if path.name == self.failing_upload:
            raise RuntimeError("upload failed")
        if path.name == "daily.json":
            self.uploaded_manifest = json.loads(path.read_text(encoding="utf-8"))
        else:
            self._assets.append(ReleaseAsset(len(self._assets) + 1, path.name))

    def delete(self, asset_id: int) -> None:
        self.events.append(("delete", str(asset_id)))


def write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "files": [],
                "archives": [
                    {"url": "https://example.com/config.zip", "exclude": ["server-only.txt"]},
                    {
                        "url": (
                            "https://github.com/Pxx500/GTNH-Translations/releases/download/"
                            "pl_PL-latest/not-the-upstream-translation.zip"
                        ),
                        "keepExisting": True,
                    },
                    {
                        "url": (
                            "https://github.com/GTNewHorizons/GTNH-Translations/releases/download/"
                            "pl_PL-latest/GTNH-pl_PL-Translation-Daily-2026-08-06+413.zip"
                        ),
                        "keepExisting": True,
                    },
                    {
                        "url": (
                            "https://github.com/GTNewHorizons/GTNH-Translations/releases/download/"
                            "de_DE-latest/GTNH-de_DE-Translation-Daily-2026-08-06+413.zip"
                        ),
                        "keepExisting": True,
                    },
                ],
                "textFiles": {},
            }
        ),
        encoding="utf-8",
    )


def test_publish_mirrors_translations_before_replacing_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "daily.json"
    write_manifest(manifest_path)
    release = FakeRelease(
        [
            ReleaseAsset(10, "GTNH-pl_PL-Translation-Daily-2026-08-04+411.zip"),
            ReleaseAsset(11, "GTNH-pl_PL-Translation-Daily-2026-08-05+412.zip"),
        ]
    )

    async def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=request.url.path.encode())

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await publish_fullpack_manifest(manifest_path, "Pxx500/DreamAssemblerXXL", release, client)

    asyncio.run(run())

    assert release.events[:4] == [
        ("ensure", ""),
        ("upload", "GTNH-pl_PL-Translation-Daily-2026-08-06+413.zip"),
        ("upload", "GTNH-de_DE-Translation-Daily-2026-08-06+413.zip"),
        ("upload", "daily.json"),
    ]
    assert release.events[4:] == [("delete", "10")]
    assert release.uploaded_manifest is not None
    archives = release.uploaded_manifest["archives"]
    assert isinstance(archives, list)
    assert archives[0] == {"url": "https://example.com/config.zip", "exclude": ["server-only.txt"]}
    assert archives[1] == {
        "url": (
            "https://github.com/Pxx500/GTNH-Translations/releases/download/"
            "pl_PL-latest/not-the-upstream-translation.zip"
        ),
        "keepExisting": True,
    }
    assert [archive["url"] for archive in archives[2:]] == [
        (
            "https://github.com/Pxx500/DreamAssemblerXXL/releases/download/fullpack-daily/"
            "GTNH-pl_PL-Translation-Daily-2026-08-06+413.zip"
        ),
        (
            "https://github.com/Pxx500/DreamAssemblerXXL/releases/download/fullpack-daily/"
            "GTNH-de_DE-Translation-Daily-2026-08-06+413.zip"
        ),
    ]


def test_publish_reuses_an_existing_translation_asset(tmp_path: Path) -> None:
    manifest_path = tmp_path / "daily.json"
    write_manifest(manifest_path)
    existing = ReleaseAsset(7, "GTNH-pl_PL-Translation-Daily-2026-08-06+413.zip")
    release = FakeRelease([existing])

    async def respond(request: httpx.Request) -> httpx.Response:
        assert "de_DE" in request.url.path
        return httpx.Response(200, content=b"translation")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await publish_fullpack_manifest(manifest_path, "Pxx500/DreamAssemblerXXL", release, client)

    asyncio.run(run())

    assert ("upload", existing.name) not in release.events
    assert ("upload", "GTNH-de_DE-Translation-Daily-2026-08-06+413.zip") in release.events


def test_failed_translation_download_does_not_replace_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "daily.json"
    write_manifest(manifest_path)
    release = FakeRelease()

    async def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await publish_fullpack_manifest(manifest_path, "Pxx500/DreamAssemblerXXL", release, client)

    try:
        asyncio.run(run())
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("missing translation download should fail")

    assert ("upload", "daily.json") not in release.events


def test_failed_translation_upload_does_not_replace_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "daily.json"
    write_manifest(manifest_path)
    failing_name = "GTNH-pl_PL-Translation-Daily-2026-08-06+413.zip"
    release = FakeRelease(failing_upload=failing_name)

    async def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"translation")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await publish_fullpack_manifest(manifest_path, "Pxx500/DreamAssemblerXXL", release, client)

    try:
        asyncio.run(run())
    except RuntimeError as error:
        assert str(error) == "upload failed"
    else:
        raise AssertionError("failed translation upload should stop publication")

    assert ("upload", "daily.json") not in release.events


def test_cleanup_keeps_two_translation_generations_and_unrelated_assets() -> None:
    assets = [
        ReleaseAsset(1, "daily.json"),
        ReleaseAsset(2, "unrelated.zip"),
        ReleaseAsset(3, "GTNH-pl_PL-Translation-Daily-2026-08-04+411.zip"),
        ReleaseAsset(4, "GTNH-de_DE-Translation-Daily-2026-08-05+412.zip"),
        ReleaseAsset(5, "GTNH-pl_PL-Translation-Daily-2026-08-06+413.zip"),
        ReleaseAsset(6, "GTNH-de_DE-Translation-Daily-2026-08-06+413.zip"),
    ]

    assert expired_translation_asset_ids(assets) == [3]
