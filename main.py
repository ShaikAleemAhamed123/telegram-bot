from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/hello")
async def helloCommandHandler():
    return {"message": "Hello, from FastAPI!"}
