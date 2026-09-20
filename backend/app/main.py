"""FastAPI application: exact-integer dispersion compensation workbench."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import solver as solver_mod
from .validation import validate_line, parse_line

app = FastAPI(
    title="色散补偿盒排布工作台 API",
    version="1.0.0",
)

# The browser app is served by the nginx container (same origin via reverse
# proxy in production); allow the Vite dev server for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/limits")
def limits() -> dict[str, Any]:
    from . import validation as v

    return {
        "stations_min": v.MIN_STATIONS,
        "stations_max": v.MAX_STATIONS,
        "boxes_max_per_station": v.MAX_BOXES,
        "scaled_min": v.MIN_SCALED,
        "scaled_max": v.MAX_SCALED,
        "decimal_places": 3,
    }


@app.post("/api/solve")
async def solve(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "status": "invalid",
                "errors": [
                    {
                        "station": None,
                        "field": "$",
                        "message": "请求体不是合法 JSON",
                    }
                ],
            },
        )

    errors = validate_line(payload)
    if errors:
        return JSONResponse(
            status_code=422,
            content={
                "status": "invalid",
                "errors": [
                    {
                        "station": rec.station,
                        "field": rec.field,
                        "message": rec.message,
                    }
                    for rec in errors
                ],
            },
        )

    result = solver_mod.solve(parse_line(payload))
    if result["status"] == "infeasible":
        return JSONResponse(status_code=409, content=result)
    return JSONResponse(status_code=200, content=result)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
