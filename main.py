from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/hello")
async def webhook(request : Request):
    data = await request.json()
    print(data)
    return "Hello There, from fastAPI"