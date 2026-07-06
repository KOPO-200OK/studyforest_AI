import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_handler, generic_error_handler, validation_error_handler
from app.core.logging import configure_logging
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware, SimpleRateLimitMiddleware
from app.routers import chat, health, questions

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url='/docs' if not settings.is_production else None,
    redoc_url=None,
)

if settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=['GET', 'POST'],
    allow_headers=['Content-Type', 'Authorization'],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
app.add_middleware(
    SimpleRateLimitMiddleware,
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

app.include_router(health.router)
app.include_router(questions.router)
app.include_router(chat.router)


@app.on_event('startup')
def startup_event() -> None:
    logger.info('%s %s started in %s mode', settings.app_name, settings.app_version, settings.app_env)
