import json
import os
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from git import Repo
from openai import AsyncOpenAI
from loguru import logger
import tempfile
from supabase import create_client, Client
from tinygen.app import is_change_good, upload_files
from tinygen.git_utils import get_diff, reset_repo
from dotenv import load_dotenv

from tinygen.openai_utils import Assistant

app = FastAPI()


load_dotenv()  # take environment variables from .env.


class InputData(BaseModel):
    repoUrl: str
    prompt: str


@app.post("/")
async def change_repo(data: InputData):
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase = None
    if url is not None:
        supabase: Client = create_client(url, key)
        supabase.table("inputs").insert(json.loads(data.model_dump_json())).execute()
    else:
        logger.warning("Supabase not configured")
    client = AsyncOpenAI()
    i = 0
    change = ""

    with tempfile.TemporaryDirectory() as tempdir:
        # Step 1: Fetch/clone repo
        repo = Repo.clone_from(data.repoUrl, tempdir)
        # Step 1.5 upload files to openai
        files = await upload_files(client, repo, Path(tempdir))
        assistant = Assistant()
        await assistant.init(
            name="tinygen",
            prompt=f"You are an assistant who fixes the problem given by the user. You do this by modifiying the following files: {(file.name for file in files if file.name is not None)}. You only make the necessary changes to fix the user's problem and preseve the functionality of the program. You may not ask questions, just make the change.",
            client=client,
            files=files,
        )

        # Step 4: Reflection via GPT
        try:
            while i < 6 and (
                i == 0 or not await is_change_good(change, data.prompt, client)
            ):
                i += 1
                logger.debug(f"Attempt {i}")
                # Step 2: Edit repo
                await assistant.run_thread(data.prompt, Path(tempdir))
                # Step 3: Calculate diff
                change = get_diff(repo)
                logger.trace(change)
                reset_repo(repo)
        finally:
            await assistant.close()
            for file in files:
                await file.close()
    if supabase is not None:
        supabase.table("outputs").insert(
            {"prompt": data.prompt, "repoUrl": data.repoUrl, "change": change}
        ).execute()
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
