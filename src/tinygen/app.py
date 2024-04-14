import json
from pathlib import Path
from git import Repo
from loguru import logger
from openai import AssistantEventHandler, OpenAI
from tinygen.consts import MODEL
from tinygen.git_utils import get_files
from tinygen.openai_utils import upload_files


def get_suggestions(client: OpenAI, repo: Repo, prompt: str, working_dir: Path):
    files = list(get_files(repo.head.commit.tree))
    openai_files = list(upload_files(client, files, working_dir))
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
                        "enum": files,
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

    class EventHandler(AssistantEventHandler):
        # def on_message_done(self, message):
        #     logger.debug(message)

        def on_text_done(self, text) -> None:
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

    assistant = client.beta.assistants.create(
        name="tinygen",
        model=MODEL,
        instructions=f"You are an assistant who fixes the problem given by the user. You do this by modifiying the following files: {files}. You only make the necessary changes to fix the user's problem and preseve the functionality of the program. You may not ask questions, just make the change.",
        tools=[{"type": "retrieval"}, TOOLS],
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
        logger.warning("No change detected")
        return False
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """You are a code reviewer. You determine if the changes are high quality using the following criteria:
                  1. The changes fix the problem in the prompt.
                  2. The changes are minimal and do not add or remove unnecessary code.
                  3. The changes do not break the original program.
                  4. The code is high quality.
                Output in JSON with the parameter is_change_good set to true or false. The change is a diff of the code, - for removed lines, + for added lines.""",
            },
            {"role": "user", "content": f"Change: {change}"},
            {"role": "user", "content": f"Problem: {prompt}"},
        ],
    )
    logger.trace(response)
    for message in response.choices:
        content = json.loads(message.message.content)
        if "is_change_good" in content:
            logger.trace(content)
            return content["is_change_good"]
    return False
