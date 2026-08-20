from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import create_db_engine, create_schema, create_session_factory
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the ChatFlow API application."""
    app_settings = settings or get_settings()
    engine = create_db_engine(app_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        create_schema(engine)
        yield
        engine.dispose()

    application = FastAPI(title="ChatFlow API", lifespan=lifespan)
    application.state.settings = app_settings
    application.state.db_engine = engine
    application.state.session_factory = session_factory
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router)
    application.include_router(chat_router)
    application.include_router(health_router)
    return application


app = create_app()
