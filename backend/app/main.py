import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import auth, content, dashboard, organisation, reviews, rules, users

settings = get_settings()
log = logging.getLogger("brandguard")

app = FastAPI(
    title="BrandGuard AI API",
    description="Brand governance and content compliance platform. The AI assists; humans decide.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

api = APIRouter(prefix="/api")
for r in (auth.router, organisation.router, users.router, *rules.routers, content.router, reviews.router,
          dashboard.router):
    api.include_router(r)


@api.get("/health", tags=["System"])
def health():
    return {"status": "ok", "ai_layer": "enabled" if settings.llm_enabled else "off (rule engine only)"}


app.include_router(api)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})


# Optionally serve the built React app (used by the Docker image / single-server deployment).
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = _dist / path
        return FileResponse(f if path and f.is_file() else _dist / "index.html")
