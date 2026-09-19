import os
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 切换工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print(f"[START] {settings.APP_NAME}")
    print(f"[API URL] http://127.0.0.1:{settings.APP_PORT}")
    print(f"[API DOCS] http://127.0.0.1:{settings.APP_PORT}/docs")
    print(f"[AI ENGINE] [{settings.LLM_PROVIDER.upper()}] Ready")
    print("=" * 60)
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=False)
