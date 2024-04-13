from tinygen import app
from fastapi.testclient import TestClient

client = TestClient(app)

DEFAULT_REPO = "https://github.com/jayhack/llm.sh"
DEFAULT_PROMPT = r"""# The program doesn't output anything in windows 10

(base) C:\Users\off99\Documents\Code\>llm list files in current dir; windows
/ Querying GPT-3200
───────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────
       │ File: temp.sh
───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   1   │
   2   │ dir
   3   │ ```
───────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────
>> Do you want to run this program? [Y/n] y

Running...


(base) C:\Users\off99\Documents\Code\>
Notice that there is no output. Is this supposed to work on Windows also?
Also it might be great if the script detects which OS or shell I'm using and try to use the appropriate command e.g. dir instead of ls because I don't want to be adding windows after every prompt."""


def get_results(
    client: TestClient,
    prompt: str,
    repo=DEFAULT_REPO,
):
    return client.post("/change/", json={"repoUrl": repo, "prompt": prompt})


def test_basic():
    result = get_results(client, DEFAULT_PROMPT)
    assert result.status_code == 200
    print(result.json())
    assert False
