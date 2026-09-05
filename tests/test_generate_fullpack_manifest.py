import asyncio
import json
import os
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

from daxxl.app_context import AppContext
from daxxl.assembler import downloader
from daxxl.assembler.platforms import zip_assembler
from daxxl.cli import generate_fullpack_manifest as generator


def test_server_asset_url_changes_with_contents_but_not_file_timestamps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/DreamAssemblerXXL")
    monkeypatch.setattr(downloader, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(generator, "RELEASE_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(zip_assembler, "SERVER_ASSETS_DIR", tmp_path / "server")
    server_file = tmp_path / "server/forge/java9args.txt"
    server_file.parent.mkdir(parents=True)
    server_file.write_text("first arguments", encoding="utf-8")

    async def resolve_maven_url(_client, mod, version) -> str:
        return f"https://nexus.gtnewhorizons.com/repository/releases/com/github/GTNewHorizons/{mod.name}/{version.version_tag}/{mod.name}-{version.version_tag}.jar"

    monkeypatch.setattr(generator, "resolve_maven_url", resolve_maven_url)

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            context = AppContext(client)
            release = context.release_service.get_release("daily")
            assert release is not None
            assembler = zip_assembler.ZipAssembler(context, release)
            config_path = downloader.get_asset_version_cache_location(*assembler.get_config())
            with ZipFile(config_path, "w") as archive:
                archive.writestr("config/txloader/load/mainmenu/version.txt", "stale")
                archive.writestr("config/GTNewHorizons/dreamcraft.cfg", "S:ModPackVersion=stale\n")
                archive.writestr("config/DreamCoreMod.properties", "displayedModpackVersion=stale\n")

        assert generator.generate_fullpack_manifest.callback is not None
        await generator.generate_fullpack_manifest.callback()
        manifest_path = tmp_path / "manifests/fullpack/daily-server.json"
        first_url = json.loads(manifest_path.read_text(encoding="utf-8"))["archives"][-1]["url"]
        os.utime(server_file, (1_600_000_000, 1_600_000_000))
        await generator.generate_fullpack_manifest.callback()
        assert json.loads(manifest_path.read_text(encoding="utf-8"))["archives"][-1]["url"] == first_url

        server_file.write_text("changed arguments", encoding="utf-8")
        await generator.generate_fullpack_manifest.callback()
        second_url = json.loads(manifest_path.read_text(encoding="utf-8"))["archives"][-1]["url"]
        assert second_url != first_url
        for url in (first_url, second_url):
            assert url.startswith("https://github.com/example/DreamAssemblerXXL/releases/download/fullpack-daily/server-assets-")
            assert (manifest_path.parent / url.rsplit("/", 1)[-1]).is_file()

    asyncio.run(run())
