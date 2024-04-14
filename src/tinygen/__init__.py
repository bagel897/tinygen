from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from git import Repo
from openai import OpenAI
from loguru import logger
import tempfile

from tinygen.app import get_suggestions, is_change_good
from tinygen.git_utils import get_diff, reset_repo

app = FastAPI()


class InputData(BaseModel):
    repoUrl: str
    prompt: str


@app.post("/")
def change_repo(data: InputData):
    client = OpenAI()
    i = 0
    change = ""
    with tempfile.TemporaryDirectory() as tempdir:
        # Step 1: Fetch/clone repo
        repo = Repo.clone_from(data.repoUrl, tempdir)
        # Step 4: Reflection via GPT
        while i < 6 and (i == 0 or not is_change_good(change, data.prompt, client)):
            i += 1
            logger.debug(f"Attempt {i}")
            # Step 2: Edit repo
            get_suggestions(client, repo, data.prompt, Path(tempdir))
            # Step 3: Calculate diff
            change = get_diff(repo)
            logger.trace(change)
            reset_repo(repo)

    # Add your code here to process the repoUrl and prompt

    return change


DEFAULT_REPO = "https://github.com/jayhack/llm.sh"
DEFAULT_PROMPT = """# The program doesn't output anything in windows 10

(base) C:\\Users\\off99\\Documents\\Code\\>llm list files in current dir; windows
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


(base) C:\\Users\\off99\\Documents\\Code\\>
Notice that there is no output. Is this supposed to work on Windows also?
Also it might be great if the script detects which OS or shell I'm using and try to use the appropriate command e.g. dir instead of ls because I don't want to be adding windows after every prompt."""

if __name__ == "__main__":
    print(change_repo(InputData(repoUrl=DEFAULT_REPO, prompt=DEFAULT_PROMPT)))
