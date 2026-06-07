from fastapi import FastAPI

from app.routers import group_router, user_router

app = FastAPI()

app.include_router(user_router.router)
app.include_router(group_router.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
