"""Read-only public demo. Run the local API separately for experiment controls."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app import app as dashboard_api

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def read_only_demo(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        return JSONResponse(status_code=403, content={
            "detail": "This public demo is read-only. Experiment execution is disabled."
        })
    if any(value.lower() not in {"true", "1", "yes", "on"}
           for value in request.query_params.getlist("demo")):
        return JSONResponse(status_code=403, content={
            "detail": "Live Kubernetes access is disabled in the public demo."
        })
    return await call_next(request)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(DIST / "index.html")


app.mount("/assets", StaticFiles(directory=DIST / "assets", check_dir=False), name="assets")
app.mount("/", dashboard_api)
