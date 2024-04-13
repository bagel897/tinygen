from tinygen import app
from fastapi.testclient import TestClient

client = TestClient(app)

DEFAULT_REPO = "https://github.com/bagel897/bagel897"


def get_results(
    client: TestClient,
    prompt: str,
    repo=DEFAULT_REPO,
):
    return client.post("/change/", json={"repoUrl": repo, "prompt": prompt})


def test_basic():
    result = get_results(client, "Add an expanation of how I went to Mt Everest")
    assert result.status_code == 200
    print(result.json())
    assert False
