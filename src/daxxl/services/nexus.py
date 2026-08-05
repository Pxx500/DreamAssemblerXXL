import httpx

from daxxl.models.gtnh_version import GTNHVersion
from daxxl.models.mod_info import GTNHModInfo

NEXUS_SEARCH_URL = "https://nexus.gtnewhorizons.com/service/rest/v1/search"


async def resolve_maven_url(client: httpx.AsyncClient, mod: GTNHModInfo, version: GTNHVersion) -> str:
    response = await client.get(
        NEXUS_SEARCH_URL,
        params={"repository": "releases", "name": mod.name, "version": version.version_tag},
    )
    response.raise_for_status()

    filename = f"{mod.name}-{version.version_tag}.jar"
    for item in response.json()["items"]:
        if item["name"] != mod.name or item["version"] != version.version_tag:
            continue
        for asset in item["assets"]:
            url = asset["downloadUrl"]
            if url.endswith(f"/{filename}"):
                return url

    raise ValueError(f"No public Maven artifact found for {mod.name}:{version.version_tag}")
