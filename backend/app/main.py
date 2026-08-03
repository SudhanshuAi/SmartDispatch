from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SmartDispatch API",
        version="0.1.0",
        description="Event-scoped vehicle dispatch backend.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "SmartDispatch API",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
