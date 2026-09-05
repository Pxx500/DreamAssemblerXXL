import hashlib
import os
from zipfile import ZIP_DEFLATED, ZipFile

import asyncclick as click
import httpx

from daxxl.app_context import AppContext
from daxxl.assembler.downloader import get_asset_version_cache_location
from daxxl.assembler.platforms.zip_assembler import ZipAssembler
from daxxl.defs import RELEASE_MANIFEST_DIR, DevRelease, ServerBrand, Side
from daxxl.fullpack_manifest import fullpack_manifest_path, write_fullpack_manifest
from daxxl.fullpack_release import RELEASE_TAG
from daxxl.services.nexus import resolve_maven_url
from daxxl.utils import normalize_archive_permissions


@click.command()
async def generate_fullpack_manifest() -> None:
    async with httpx.AsyncClient(http2=True) as client:
        context = AppContext(client)
        release = context.release_service.get_release(DevRelease.DAILY.value)
        if release is None:
            raise click.ClickException("Daily release not found")

        assembler = ZipAssembler(context, release)
        resolved_private_mods: set[tuple[str, str]] = set()
        for side in (Side.CLIENT_JAVA9, Side.SERVER_JAVA9):
            for mod, version in assembler.get_mods(side):
                key = mod.name, version.version_tag
                if not mod.private or key in resolved_private_mods:
                    continue
                version.maven_url = await resolve_maven_url(client, mod, version)
                resolved_private_mods.add(key)

        config, config_version = assembler.get_config()
        config_path = get_asset_version_cache_location(config, config_version)
        if not config_path.exists():
            assert config_version.browser_download_url is not None
            await context.downloader._download_file(config_version.browser_download_url, config_path, {})

        manifest_path = RELEASE_MANIFEST_DIR / f"{DevRelease.DAILY.value}.json"
        write_fullpack_manifest(manifest_path, assembler)

        server_assets_path = fullpack_manifest_path(manifest_path).with_name("server-assets.zip")
        with ZipFile(server_assets_path, "w", compression=ZIP_DEFLATED) as archive:
            await assembler.add_server_assets(archive, ServerBrand.forge, Side.SERVER_JAVA9)
            await normalize_archive_permissions(archive)

        # Ignore ZIP timestamps so unchanged contents reuse the same cached asset.
        digest = hashlib.sha256()
        with ZipFile(server_assets_path) as archive:
            for filename in sorted(archive.namelist()):
                digest.update(filename.encode("utf-8") + b"\0")
                digest.update(hashlib.sha256(archive.read(filename)).digest())
        server_assets_path = server_assets_path.replace(server_assets_path.with_name(f"server-assets-{digest.hexdigest()}.zip"))

        repository = os.environ.get("GITHUB_REPOSITORY", "Pxx500/DreamAssemblerXXL")
        server_assets_url = f"https://github.com/{repository}/releases/download/{RELEASE_TAG}/{server_assets_path.name}"
        write_fullpack_manifest(
            manifest_path,
            assembler,
            side=Side.SERVER_JAVA9,
            server_assets_url=server_assets_url,
        )


if __name__ == "__main__":
    generate_fullpack_manifest()
