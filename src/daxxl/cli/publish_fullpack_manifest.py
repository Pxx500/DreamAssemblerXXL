import os
from pathlib import Path

import asyncclick as click
import httpx

from daxxl.fullpack_release import GitHubRelease, publish_fullpack_manifest


@click.command()
@click.argument("manifest", type=click.Path(path_type=Path))
async def publish(manifest: Path) -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    async with httpx.AsyncClient(follow_redirects=True) as client:
        await publish_fullpack_manifest(manifest, repository, GitHubRelease(repository), client)


if __name__ == "__main__":
    publish()
