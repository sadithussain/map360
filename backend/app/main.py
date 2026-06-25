from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import group_router, map_router, user_router

app = FastAPI()

# Allow the Vite dev server to call the API from the browser during local
# development. Tighten or replace these origins for staging/production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return schema validation failures as a single readable message.

    FastAPI's default body is a list of error objects that is awkward to
    surface in a UI. This flattens those into one ``detail`` string (for
    example, "password: String should have at least 8 characters") so clients
    can show the user exactly what was wrong.
    """
    messages = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = location[-1] if location else "request"
        message = error.get("msg", "Invalid value")
        messages.append(f"{field}: {message}")

    detail = " ".join(messages) if messages else "Invalid request."

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )


app.include_router(user_router.router)
app.include_router(group_router.router)
app.include_router(map_router.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
