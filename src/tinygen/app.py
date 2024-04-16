import json
from pathlib import Path
from git import Repo
from loguru import logger
from openai import AsyncOpenAI
from tinygen.consts import MODEL
from tinygen.git_utils import get_files
from tinygen.openai_utils import File


async def upload_files(client: AsyncOpenAI, repo: Repo, working_dir: Path):
    files = []
    for path in get_files(repo.head.commit.tree):
        file = File()
        await file.init(working_dir / path, working_dir, client)
        files.append(file)
    return files


async def is_change_good(change: str, prompt: str, client: AsyncOpenAI) -> bool:
    if change == "":
        logger.warning("No change detected")
        return False
    response = await client.chat.completions.create(
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
