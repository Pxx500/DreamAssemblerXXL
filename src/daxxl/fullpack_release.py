import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol
from urllib.parse import unquote, urlparse

import httpx

from daxxl.utils import atomic_write_text

TRANSLATIONS_REPOSITORY = ("GTNewHorizons", "GTNH-Translations")
RELEASE_TAG = "fullpack-daily"
TRANSLATION_FILENAME = re.compile(r"^GTNH-[^-]+-Translation-Daily-(?P<date>\d{4}-\d{2}-\d{2})\+(?P<build>\d+)\.zip$")


@dataclass(frozen=True)
class ReleaseAsset:
    id: int
    name: str


class FullpackRelease(Protocol):
    def ensure_exists(self) -> None: ...

    def assets(self) -> list[ReleaseAsset]: ...

    def upload(self, path: Path, *, clobber: bool = False) -> None: ...

    def delete(self, asset_id: int) -> None: ...


class GitHubRelease:
    def __init__(self, repository: str, tag: str = RELEASE_TAG) -> None:
        self.repository = repository
        self.tag = tag

    def ensure_exists(self) -> None:
        result = subprocess.run(
            ["gh", "release", "view", self.tag, "--repo", self.repository],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            subprocess.run(
                [
                    "gh",
                    "release",
                    "create",
                    self.tag,
                    "--repo",
                    self.repository,
                    "--prerelease",
                    "--title",
                    "Full-pack daily manifest",
                    "--notes",
                    "Generated from the current GTNH daily mod list.",
                ],
                check=True,
            )

    def assets(self) -> list[ReleaseAsset]:
        result = subprocess.run(
            ["gh", "api", f"repos/{self.repository}/releases/tags/{self.tag}"],
            capture_output=True,
            text=True,
            check=True,
        )
        release = json.loads(result.stdout)
        return [ReleaseAsset(asset["id"], asset["name"]) for asset in release["assets"]]

    def upload(self, path: Path, *, clobber: bool = False) -> None:
        command = ["gh", "release", "upload", self.tag, str(path), "--repo", self.repository]
        if clobber:
            command.append("--clobber")
        subprocess.run(command, check=True)

    def delete(self, asset_id: int) -> None:
        subprocess.run(
            ["gh", "api", "--method", "DELETE", f"repos/{self.repository}/releases/assets/{asset_id}"],
            check=True,
        )


def _translation_filename(url: str) -> str | None:
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if parsed.netloc != "github.com" or len(parts) < 6 or tuple(parts[:2]) != TRANSLATIONS_REPOSITORY:
        return None
    if parts[2:4] != ["releases", "download"]:
        return None
    return unquote(parts[-1])


def _mirrored_url(repository: str, filename: str) -> str:
    return f"https://github.com/{repository}/releases/download/{RELEASE_TAG}/{filename}"


def expired_translation_asset_ids(assets: list[ReleaseAsset]) -> list[int]:
    versioned_assets: list[tuple[ReleaseAsset, tuple[str, int]]] = []
    for asset in assets:
        match = TRANSLATION_FILENAME.fullmatch(asset.name)
        if match is not None:
            versioned_assets.append((asset, (match["date"], int(match["build"]))))

    retained_generations = set(sorted({generation for _, generation in versioned_assets}, reverse=True)[:2])
    return [asset.id for asset, generation in versioned_assets if generation not in retained_generations]


async def publish_fullpack_manifest(
    manifest_path: Path,
    repository: str,
    release: FullpackRelease,
    client: httpx.AsyncClient,
    companion_assets: Sequence[Path] = (),
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    release.ensure_exists()
    existing_names = {asset.name for asset in release.assets()}

    with TemporaryDirectory() as temporary_directory:
        for archive in manifest["archives"]:
            filename = _translation_filename(archive["url"])
            if filename is None:
                continue

            if filename not in existing_names:
                response = await client.get(archive["url"])
                response.raise_for_status()
                asset_path = Path(temporary_directory) / filename
                asset_path.write_bytes(response.content)
                release.upload(asset_path)
                existing_names.add(filename)

            archive["url"] = _mirrored_url(repository, filename)

    for asset in companion_assets:
        release.upload(asset, clobber=True)
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False))
    release.upload(manifest_path, clobber=True)
    for asset_id in expired_translation_asset_ids(release.assets()):
        release.delete(asset_id)
