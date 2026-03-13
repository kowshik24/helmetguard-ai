from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app.db.init_db import init_db
from api.app.routes.health import router as health_router
from api.app.routes.jobs import router as jobs_router
from api.app.routes.web import router as web_router
from shared.config import get_settings
from shared.logging import configure_logging

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(web_router)
