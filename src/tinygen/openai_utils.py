"""OpenAI helpers"""

from pathlib import Path
from loguru import logger


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
