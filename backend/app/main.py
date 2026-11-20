import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as agents_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = "تعذّر إكمال الطلب الآن. يُرجى المحاولة مرة أخرى بعد قليل."


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Citizen Complaint Management System", version="0.1.0")

    # The React dev server runs on a different origin, so the browser needs CORS.
    # Origins are configurable through CORS_ORIGINS (comma-separated) and default to Vite.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return field-level errors without echoing the submitted body.

        Pydantic includes the invalid input in ``errors()``; that could reflect a national ID
        or phone number back to the client (and into access logs), so it is stripped here.
        """
        errors = [
            {key: value for key, value in error.items() if key not in {"input", "ctx"}}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Last resort: Arabic 503 instead of a 500 or a stack trace."""
        logger.error("unhandled error path=%s type=%s", request.url.path, type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": UNEXPECTED_ERROR})

    app.include_router(agents_router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness: the process is up. Does not touch providers or the store."""
        return {"status": "ok", "env": settings.app_env}

    @app.get("/ready", tags=["system"])
    def ready() -> JSONResponse:
        """Readiness: knowledge is loaded and the offline fallback is wired.

        A missing paid provider is *not* fatal by design: the service answers in offline mode
        and reports ``paid_provider_available=false`` so an operator can notice it.
        """
        from app.services.runtime import get_runtime

        report = get_runtime().readiness()
        status_code = 200 if report["status"] == "ready" else 503
        return JSONResponse(status_code=status_code, content=report)

    return app


app = create_app()
