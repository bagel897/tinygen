import json
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

MODEL = "gpt-4-turbo"


class InputData(BaseModel):
    repoUrl: str
    prompt: str


def get_diff(repo: Repo):
    diff = repo.index.diff(None, create_patch=True, unified=1000)
    result = ""
    for diff in diff.iter_change_type("M"):
        result += str(diff)
    return result


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
        logger.trace(f"Uploaded {name}")
        yield client.files.create(
            file=(name, content),
            purpose="assistants",
        )


def get_suggestions(client: OpenAI, repo: Repo, prompt: str, working_dir: Path):
    files = list(get_files(repo.head.commit.tree))
    openai_files = list(upload_files(client, files, working_dir))
    TOOLS = {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Modifies a file in the repository by writing new content to it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "enum": files,
                        "description": "The original filename relative to the root of the repository",
                    },
                    "content": {
                        "type": "string",
                        "description": "The new content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    }

    class EventHandler(AssistantEventHandler):
        # def on_message_done(self, message):
        #     logger.debug(message)

        def on_text_done(self, text: Text) -> None:
            logger.debug(text.value)
            for annotation in text.annotations:
                logger.trace(annotation)
                if annotation.type == "file_path":
                    file_data = client.files.content(annotation.file_path.file_id)
                    logger.debug(file_data)
                    self.write_file(file_data.filename, file_data.read())

            return super().on_text_done(text)

        def write_file(self, path, content):
            full_path = working_dir.joinpath(path)
            if full_path.exists():
                full_path.write_text(content)
            return path

        def on_tool_call_done(
            self,
            tool_call,
        ) -> None:
            if tool_call.type == "function":
                if tool_call.function.name == "write_file":
                    logger.trace(tool_call.function.arguments)
                    arguments = json.loads(tool_call.function.arguments)
                    logger.trace(arguments)
                    self.write_file(
                        arguments["path"],
                        arguments["content"],
                    )
            return super().on_tool_call_done(tool_call)

        # def on_event(self, event) -> None:
        #     logger.debug(event)
        #     return super().on_event(event)

        # @override
        # def on_text_delta(self, delta, snapshot):
        #     logger.debug(delta.value)

    assistant = client.beta.assistants.create(
        name="tinygen",
        model=MODEL,
        instructions=f"Fix the issue specified by the user. Modify the following files: {files}. Make only the necessary changes.",
        tools=[{"type": "code_interpreter"}, TOOLS],
        file_ids=[file.id for file in openai_files],
    )
    try:

        thread = client.beta.threads.create(
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        with client.beta.threads.runs.stream(
            thread_id=thread.id, assistant_id=assistant.id, event_handler=EventHandler()
        ) as stream:
            stream.until_done()
    finally:
        client.beta.assistants.delete(assistant.id)
        for file in openai_files:
            client.files.delete(file.id)


def is_change_good(change: str, prompt: str, client: OpenAI) -> bool:
    if change == "":
        return False
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Does the following change fix the issue without extra changes? Output in JSON with the parameter is_change_good set to true or false.",
            },
            {"role": "user", "content": f"Change: {change}"},
            {"role": "user", "content": f"Prompt: {prompt}"},
        ],
    )
    logger.trace(response)
    for message in response.choices:
        content = json.loads(message.message.content)
        if "is_change_good" in content:
            logger.trace(content)
            return content["is_change_good"]
    return False


def reset_repo(repo: Repo):
    repo.git.reset("--hard")
    repo.git.clean("-fd")


@app.post("/change")
def change_repo(data: InputData):
    client = OpenAI()
    i = 0
    change = ""
    with tempfile.TemporaryDirectory() as tempdir:
        # Step 1: Fetch/clone repo
        repo = Repo.clone_from(data.repoUrl, tempdir)
        # Step 4: Reflection via GPT
        while i < 6 and not is_change_good(change, data.prompt, client):
            # Step 2: Edit repo
            get_suggestions(client, repo, data.prompt, Path(tempdir))
            # Step 3: Calculate diff
            change = get_diff(repo)
            logger.trace(change)
            reset_repo(repo)
            i += 1

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
