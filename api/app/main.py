"""FastAPI 入口：健康检查、精确求解接口。"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .solver import solve
from .validation import ValidationReport, parse_json_decimal, validate_payload

app = FastAPI(title="色散补偿盒排布工作台 API", version="1.0.0")

# 开发态允许跨域；生产由 Compose 内网 + Web 反代访问。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.post("/api/solve")
async def solve_route(request: Request) -> JSONResponse:
    body = await request.body()
    raw = parse_json_decimal(body)
    try:
        increments, stations = validate_payload(raw)
    except ValidationReport as report:
        return JSONResponse(
            status_code=422,
            content={"status": "invalid", "errors": report.errors},
        )

    result = solve(increments, stations)
    return JSONResponse(status_code=200, content=result)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "dcm-workbench-api", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("API_PORT", "8000")),
    )
