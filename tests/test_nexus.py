import asyncio

import httpx

from daxxl.models.gtnh_version import GTNHVersion
from daxxl.models.mod_info import GTNHModInfo
from daxxl.services.nexus import resolve_maven_url


def test_private_mod_resolves_to_its_main_public_maven_jar() -> None:
    version = GTNHVersion(version_tag="0.29.7-GTNH", filename="Automagy-0.29.7-GTNH.jar")
    mod = GTNHModInfo(
        name="Automagy-GTNH",
        latest_version=version.version_tag,
        private=True,
        repo_url="https://github.com/GTNewHorizons/Automagy-GTNH",
        versions=[version],
    )
    expected_url = "https://nexus.gtnewhorizons.com/repository/releases/tuhljin/automagy/Automagy-GTNH/0.29.7-GTNH/Automagy-GTNH-0.29.7-GTNH.jar"

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["repository"] == "releases"
        assert request.url.params["name"] == mod.name
        assert request.url.params["version"] == version.version_tag
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "group": "tuhljin.automagy",
                        "name": mod.name,
                        "version": version.version_tag,
                        "assets": [
                            {"downloadUrl": expected_url.removesuffix(".jar") + "-dev.jar"},
                            {"downloadUrl": expected_url},
                            {"downloadUrl": expected_url.removesuffix(".jar") + "-sources.jar"},
                        ],
                    }
                ]
            },
        )

    async def resolve() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await resolve_maven_url(client, mod, version)

    assert asyncio.run(resolve()) == expected_url
