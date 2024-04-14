"""OpenAI helpers"""

import json
from pathlib import Path
from loguru import logger
import openai
from openai import OpenAI

from tinygen.consts import MODEL


class File:
    path: Path
    name: str
    openai = None
    client: OpenAI

    def __init__(self, path: Path, working_dir: Path, client: OpenAI) -> None:
        self.path = path
        self.name = str(path.relative_to(working_dir))
        content = path.read_bytes()
        self.client = client
        if len(content) == 0:
            self.openai = None
        else:
            logger.trace(f"Uploaded {self.name}")
            self.client = client
            self.openai = client.files.create(
                file=(self.name, content),
                purpose="assistants",
            )

    def close(self):
        if self.openai is not None:
            self.client.files.delete(self.openai.id)


class EventHandler(openai.AssistantEventHandler):
    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir
        super().__init__()

    def on_text_done(self, text) -> None:
        logger.debug(text.value)
        return super().on_text_done(text)

    def write_file(self, path, content):
        full_path = self.working_dir.joinpath(path)
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


class Assistant:
    client: OpenAI

    def __init__(
        self, name: str, prompt: str, client: OpenAI, files: list[File]
    ) -> None:
        self.client = client
        TOOLS = {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Writes a new version of a file in the repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "enum": [
                                file.name for file in files if file.openai is not None
                            ],
                            "description": "The original filename relative to the root of the repository",
                        },
                        "content": {
                            "type": "string",
                            "description": "The new version of the file",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        }
        self.assistant = self.client.beta.assistants.create(
            name=name,
            model=MODEL,
            instructions=prompt,
            tools=[{"type": "retrieval"}, TOOLS],
            file_ids=[file.openai.id for file in files if file.openai is not None],
        )

    def run_thread(self, prompt: str, working_dir: Path):

        thread = self.client.beta.threads.create(
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        with self.client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=self.assistant.id,
            event_handler=EventHandler(working_dir),
        ) as stream:
            stream.until_done()

    def close(self):
        self.client.beta.assistants.delete(self.assistant.id)
