from fastapi import FastAPI

app = FastAPI()

@app.post("/hello")
async def webhook(request):
    data = await request.json()
    print(data)
    return "Hello There, from fastAPI"