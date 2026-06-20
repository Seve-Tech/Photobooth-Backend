import sys
import asyncio
import uvicorn

from app.app_factory import create_app
from app.core.config import settings

app = create_app()

async def run_migration():
    import migrate
    await migrate.main()

async def run_seed():
    import seed_db
    await seed_db.main()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        asyncio.run(run_migration())
    elif len(sys.argv) > 1 and sys.argv[1] == "seed":
        asyncio.run(run_seed())
    else:
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level="debug" if settings.debug else "info",
        )
