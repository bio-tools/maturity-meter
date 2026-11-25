import asyncio

import httpx

from maturity_meter.external import http
from maturity_meter.external.ingestors.github import GitHubIngestor


def test_github_repository_redirect_uses_new_name_for_related_metadata():
    paths = []
    old_repo = "/repos/old-owner/old-name"
    new_repo = "/repos/new-owner/new-name"

    def respond(request):
        path = request.url.path
        paths.append(path)
        if path == old_repo:
            return httpx.Response(301, headers={"Location": "/repositories/123"})
        if path == "/repositories/123":
            return httpx.Response(
                200, json={"full_name": "new-owner/new-name", "default_branch": "main"}
            )
        if path == "/search/issues":
            expected_query = "repo:new-owner/new-name type:issue state:open"
            assert request.url.params["q"] == expected_query
            return httpx.Response(200, json={"total_count": 2})
        assert path.startswith(f"{new_repo}/")
        return httpx.Response(404, json={"message": "Not Found"})

    async def fetch():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            token = http._client.set(client)
            try:
                return await GitHubIngestor("old-owner", "old-name").fetch()
            finally:
                http._client.reset(token)

    result = asyncio.run(fetch())

    assert paths[:2] == [old_repo, "/repositories/123"]
    assert result["repo"]["full_name"] == "new-owner/new-name"
    assert result["open_issues"] == 2
