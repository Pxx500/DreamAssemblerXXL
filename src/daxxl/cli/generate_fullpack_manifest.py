import asyncclick as click
import httpx

from daxxl.app_context import AppContext
from daxxl.assembler.downloader import get_asset_version_cache_location
from daxxl.assembler.platforms.zip_assembler import ZipAssembler
from daxxl.defs import RELEASE_MANIFEST_DIR, DevRelease, Side
from daxxl.fullpack_manifest import write_fullpack_manifest
from daxxl.services.nexus import resolve_maven_url


@click.command()
async def generate_fullpack_manifest() -> None:
    async with httpx.AsyncClient(http2=True) as client:
        context = AppContext(client)
        release = context.release_service.get_release(DevRelease.DAILY.value)
        if release is None:
            raise click.ClickException("Daily release not found")

        assembler = ZipAssembler(context, release)
        for mod, version in assembler.get_mods(Side.CLIENT_JAVA9):
            if mod.private:
                version.maven_url = await resolve_maven_url(client, mod, version)

        config, config_version = assembler.get_config()
        config_path = get_asset_version_cache_location(config, config_version)
        if not config_path.exists():
            assert config_version.browser_download_url is not None
            await context.downloader._download_file(config_version.browser_download_url, config_path, {})

        write_fullpack_manifest(RELEASE_MANIFEST_DIR / f"{DevRelease.DAILY.value}.json", assembler)


if __name__ == "__main__":
    generate_fullpack_manifest()
