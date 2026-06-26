import subprocess, sys

pkgs = ["fastapi", "uvicorn", "sqlalchemy", "aiosqlite", "pydantic", "hypothesis", "pytest", "pytest_asyncio", "httpx"]
for p in pkgs:
    try:
        m = __import__(p)
        print(p, getattr(m, "__version__", "?"))
    except ImportError:
        print(p, "NOT INSTALLED")
