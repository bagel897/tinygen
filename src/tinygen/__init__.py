import os
from pathlib import Path
from tarfile import SUPPORTED_TYPES
from fastapi import FastAPI
from openai.types.beta.threads import Text
from pydantic import BaseModel
from git import Repo
from openai import OpenAI, AssistantEventHandler
from loguru import logger
import tempfile

app = FastAPI()

MODEL = "gpt-3.5-turbo"


class InputData(BaseModel):
    repoUrl: str
    prompt: str


def get_diff(repo: Repo):
    diff = repo.index.diff(None)
    return diff


TOOLS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Reads a file and returns its contents",
        "parameters": [
            {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                },
                "required": ["file"],
            }
        ],
    }
]

SUPPORTED_TYPES = [".c", ".cpp", ".py", ".sh", ".md", ".html", ".txt"]


def get_files(tree):
    for entry in tree:
        if entry.type == "tree":
            yield from get_files(entry)
        else:
            if entry.name.endswith(tuple(SUPPORTED_TYPES)):

                yield entry.path


def upload_files(client, files, working_dir: Path):
    for file in files:
        name = file
        full_path = (working_dir / file).resolve()
        content = full_path.read_bytes()
        if len(content) == 0:
            continue
        logger.debug(name, full_path, content)
        yield client.files.create(
            file=(name, content),
            purpose="assistants",
        )


def get_suggestions(client: OpenAI, repo: Repo, prompt: str, working_dir: Path):
    files = list(get_files(repo.head.commit.tree))
    os.system(f"ls -l {working_dir}")

    openai_files = list(upload_files(client, files, working_dir))

    class EventHandler(AssistantEventHandler):
        def on_message_done(self, message):
            logger.debug(message)

        def on_text_done(self, text: Text) -> None:
            logger.debug(text)
            for annotation in text.annotations:
                logger.debug(annotation)
                if annotation.type == "file_path":
                    file_data = client.files.content(annotation.file_path.file_id)
                    working_dir.joinpath(file_data.filename).write_text(
                        file_data.read()
                    )
            return super().on_text_done(text)

        # def on_event(self, event) -> None:
        #     logger.debug(event)
        #     return super().on_event(event)

        # @override
        # def on_text_delta(self, delta, snapshot):
        #     logger.debug(delta.value)

    assistant = client.beta.assistants.create(
        name="tinygen",
        model=MODEL,
        description="Edit the files to apply the requested change",
        tools=[{"type": "code_interpreter"}],
        file_ids=[file.id for file in openai_files],
    )
    thread = client.beta.threads.create(
        messages=[
            {"role": "user", "content": "prompt:\n" + prompt},
        ],
    )
    with client.beta.threads.runs.stream(
        thread_id=thread.id, assistant_id=assistant.id, event_handler=EventHandler()
    ) as stream:
        stream.until_done()


@app.post("/change")
def change_repo(data: InputData):
    client = OpenAI()

    with tempfile.TemporaryDirectory() as tempdir:
        # Step 1: Fetch/clone repo
        repo = Repo.clone_from(data.repoUrl, tempdir)

        # Step 2: Edit repo
        get_suggestions(client, repo, data.prompt, Path(tempdir))
        # Step 3: Calculate diff
        result = get_diff(repo)
        # TODO actually get unified diff from diff object
        logger.debug(result)
        # Step 4: Reflection via GPT

    # Add your code here to process the repoUrl and prompt

    return result
