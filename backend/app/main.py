import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.routers import activity_router, group_router, map_router, user_router

logger = logging.getLogger(__name__)

app = FastAPI()

# Allow the Vite / React dev server to call this API from the browser.
# localhost and 127.0.0.1 are different origins to the browser, so both
# must be listed explicitly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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


_DB_UNAVAILABLE_DETAIL = (
    "Database unavailable. Check DATABASE_URL in backend/.env "
    "(use your Supabase Postgres connection string with the "
    "postgresql+asyncpg:// scheme)."
)

_CORS_DEV_ORIGINS = frozenset(
    {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
)


def _cors_headers_for(request: Request) -> dict[str, str]:
    """CORS headers for responses returned outside the normal middleware path."""
    origin = request.headers.get("origin")
    if origin not in _CORS_DEV_ORIGINS:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
    }


@app.middleware("http")
async def catch_database_connection_errors(request: Request, call_next):
    """Turn DB connection failures into a JSON 503 with CORS-friendly headers.

    Connection refusals from a bad DATABASE_URL otherwise become opaque 500s
    that browsers often report as CORS errors.
    """
    try:
        return await call_next(request)
    except (OSError, SQLAlchemyError):
        logger.exception(
            "Database connection failed while handling %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": _DB_UNAVAILABLE_DETAIL},
            headers=_cors_headers_for(request),
        )


app.include_router(user_router.router)
app.include_router(group_router.router)
app.include_router(map_router.router)
app.include_router(activity_router.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
