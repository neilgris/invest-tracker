from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from database import init_db
from scheduler import start_scheduler
from routers import trades, positions, quotes, stats, analysis

app = FastAPI(title="Invest Tracker", description="投资追踪平台")

# 注册路由
app.include_router(trades.router)
app.include_router(positions.router)
app.include_router(quotes.router)
app.include_router(stats.router)
app.include_router(analysis.router)

# 静态文件（前端）
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.on_event("startup")
def startup():
    init_db()
    start_scheduler()


@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    """SPA fallback 中间件：非 /api 路径返回 index.html"""
    response = await call_next(request)
    
    # 只处理 404 且非 API 路径
    if response.status_code == 404 and not request.url.path.startswith("/api"):
        static_dir = Path(__file__).parent / "static"
        # 尝试匹配静态文件
        rel_path = request.url.path.lstrip("/")
        file_path = static_dir / rel_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # fallback 到 index.html
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
    
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
