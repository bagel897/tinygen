from fastapi import FastAPI
from pydantic import BaseModel
from git import Repo
import tempfile

app = FastAPI()


class InputData(BaseModel):
    repoUrl: str
    prompt: str


@app.post("/change")
def change_repo(data: InputData):
    with tempfile.TemporaryDirectory() as tempdir:
        # Step 1: Fetch/clone repo
        repo = Repo.clone_from(data.repoUrl, tempdir)
        # Step 2: Edit repo
        # Step 3: Calculate diff
        result = repo.index.diff(None)
        # TODO actually get unified diff from diff object
        print(result)
        # Step 4: Reflection via GPT

    # Add your code here to process the repoUrl and prompt

    return result
