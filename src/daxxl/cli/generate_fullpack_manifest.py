import asyncclick as click

from daxxl.cli._assemble import generate_dev_release_manifest
from daxxl.defs import DevRelease


@click.command()
async def generate_fullpack_manifest() -> None:
    await generate_dev_release_manifest(DevRelease.DAILY)


if __name__ == "__main__":
    generate_fullpack_manifest()
