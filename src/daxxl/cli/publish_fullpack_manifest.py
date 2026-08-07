import os
from pathlib import Path

import asyncclick as click
import httpx

from daxxl.fullpack_release import GitHubRelease, publish_fullpack_manifest


@click.command()
@click.argument("manifest", type=click.Path(path_type=Path))
@click.argument("companion_assets", nargs=-1, type=click.Path(path_type=Path))
async def publish(manifest: Path, companion_assets: tuple[Path, ...]) -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    async with httpx.AsyncClient(follow_redirects=True) as client:
        await publish_fullpack_manifest(
            manifest,
            repository,
            GitHubRelease(repository),
            client,
            companion_assets,
        )


if __name__ == "__main__":
    publish()
