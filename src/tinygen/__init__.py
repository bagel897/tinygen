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

MODEL = "gpt-3.5-turbo"


class InputData(BaseModel):
    repoUrl: str
    prompt: str


def get_diff(repo: Repo):
    diff = repo.index.diff(None)
    return diff


TOOLS = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Writes to a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The original filename relative to the root of the repository",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
}


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
        logger.debug(f"Uploaded {name}")
        yield client.files.create(
            file=(name, content),
            purpose="assistants",
        )


def get_suggestions(client: OpenAI, repo: Repo, prompt: str, working_dir: Path):
    files = list(get_files(repo.head.commit.tree))
    openai_files = list(upload_files(client, files, working_dir))

    class EventHandler(AssistantEventHandler):
        # def on_message_done(self, message):
        #     logger.debug(message)

        def on_text_done(self, text: Text) -> None:
            logger.debug(text)
            for annotation in text.annotations:
                logger.debug(annotation)
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
                arguments = json.loads(tool_call.function.arguments)
                logger.debug(arguments)

                self.write_file(
                    arguments["path"],
                    arguments["content"],
                )
            return super().on_tool_call_done(tool_call)

        def on_tool_call_delta(self, delta, snapshot):
            if delta.type == "code_interpreter":
                if delta.code_interpreter.input:
                    print(delta.code_interpreter.input, end="", flush=True)
                if delta.code_interpreter.outputs:
                    print("\n\noutput >", flush=True)
                    for output in delta.code_interpreter.outputs:
                        if output.type == "logs":
                            print(f"\n{output.logs}", flush=True)

        # def on_event(self, event) -> None:
        #     logger.debug(event)
        #     return super().on_event(event)

        # @override
        # def on_text_delta(self, delta, snapshot):
        #     logger.debug(delta.value)

    assistant = client.beta.assistants.create(
        name="tinygen",
        model=MODEL,
        description="Modify the given files to fix the problem",
        tools=[{"type": "code_interpreter"}, {"type": "retrieval"}, TOOLS],
        file_ids=[file.id for file in openai_files],
    )
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "assistant",
                "content": f"Modify the following files to fix the problem: {files}",
            },
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
    change_repo(InputData(repoUrl=DEFAULT_REPO, prompt=DEFAULT_PROMPT))
