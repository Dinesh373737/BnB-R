from fastapi import FastAPI
from .router import router

app = FastAPI(title="GridMind Scenario Runner (Isolated)", version="1.0.0")

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Scenario Runner Module is active. Go to /docs to test the API."}
