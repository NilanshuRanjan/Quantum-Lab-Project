from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router

app = FastAPI(title="SmartGrid-QAOA", version="0.1.0")
app.include_router(router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_config() -> Response:
    return Response(status_code=204)


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index() -> HTMLResponse:
    index_path = frontend_dir / "index.html"
    if not index_path.exists():
        return HTMLResponse(content="<html><body><h1>SmartGrid-QAOA</h1></body></html>")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)
