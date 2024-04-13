from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class InputData(BaseModel):
    repoUrl: str
    prompt: str


@app.post("/change")
def change_repo(data: InputData):
    # Step 1: Fetch/clone repo
    # Step 2: Edit repo
    # Step 3: Calculate diff
    # Step 4: Reflection via GPT

    # Add your code here to process the repoUrl and prompt

    return {"message": "Data processed successfully"}
