import hashlib
import json
import os
from zipfile import ZIP_DEFLATED, ZipFile

import asyncclick as click
import httpx

from daxxl.app_context import AppContext
from daxxl.assembler.platforms.zip_assembler import ZipAssembler
from daxxl.defs import RELEASE_MANIFEST_DIR, DevRelease, ServerBrand, Side
from daxxl.exceptions import NoModAssetFound
from daxxl.fullpack_manifest import fullpack_config_cache_path, fullpack_manifest_path, prepare_fullpack_config, write_fullpack_manifest
from daxxl.fullpack_release import RELEASE_TAG
from daxxl.services.nexus import resolve_maven_url
from daxxl.utils import normalize_archive_permissions


@click.command()
@click.option("--config-cache-info", is_flag=True, help="Print the required config cache path and key as JSON without generating manifests.")
async def generate_fullpack_manifest(config_cache_info: bool = False) -> None:
    async with httpx.AsyncClient(http2=True) as client:
        context = AppContext(client)
        release = context.release_service.get_release(DevRelease.DAILY.value)
        if release is None:
            raise click.ClickException("Daily release not found")

        assembler = ZipAssembler(context, release)
        if config_cache_info:
            path = fullpack_config_cache_path(assembler)
            click.echo(json.dumps({"path": path.as_posix(), "key": path.stem}))
            return

        fullpack_sides = Side.CLIENT_JAVA9.valid_mod_sides() | Side.SERVER_JAVA9.valid_mod_sides()
        missing = []
        for name, selected in (release.github_mods | release.external_mods).items():
            if selected.side is not None and selected.side not in fullpack_sides:
                continue
            try:
                mod = context.assets.get_mod(name)
            except NoModAssetFound:
                missing.append(f"{name}:{selected.version}")
                continue
            if (selected.side or mod.side) in fullpack_sides and not mod.has_version(selected.version):
                missing.append(f"{name}:{selected.version}")
        if missing:
            raise click.ClickException(f"Missing daily mod versions: {', '.join(missing)}")

        resolved_private_mods: set[tuple[str, str]] = set()
        for side in (Side.CLIENT_JAVA9, Side.SERVER_JAVA9):
            for mod, version in assembler.get_mods(side):
                key = mod.name, version.version_tag
                if not mod.private or key in resolved_private_mods:
                    continue
                version.maven_url = await resolve_maven_url(client, mod, version)
                resolved_private_mods.add(key)

        config_path = await prepare_fullpack_config(assembler)

        manifest_path = RELEASE_MANIFEST_DIR / f"{DevRelease.DAILY.value}.json"
        write_fullpack_manifest(manifest_path, assembler, asset_path=lambda *_: config_path)

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
            asset_path=lambda *_: config_path,
            side=Side.SERVER_JAVA9,
            server_assets_url=server_assets_url,
        )


if __name__ == "__main__":
    generate_fullpack_manifest()
