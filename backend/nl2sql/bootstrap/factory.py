"""Application composition and importable multi-process Uvicorn factory."""

import logging
import os
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI

from nl2sql.api.app import create_app as create_transport
from nl2sql.application.ports import ApplicationResources, ModelProvider, RateLimiter
from nl2sql.bootstrap.managed import build_managed_resources
from nl2sql.bootstrap.office_checks import office_preflight
from nl2sql.bootstrap.resources import build_resources
from nl2sql.infrastructure.rate_limit import build_rate_limiter
from nl2sql.settings import Settings, apply_environment_file, load_settings


def create_app(
    settings: Settings | None = None,
    model: ModelProvider | None = None,
    resources_factory: Callable[[Settings, ModelProvider | None], ApplicationResources]
    | None = None,
    rate_limiter_factory: Callable[[Settings], RateLimiter] = build_rate_limiter,
) -> FastAPI:
    """Wire typed adapters outside transport; allocation occurs in lifespan startup."""
    configuration = settings or Settings()
    office_preflight(configuration)
    factory = resources_factory or (
        build_managed_resources if configuration.metadata_root is not None else build_resources
    )
    return create_transport(configuration, model, factory, rate_limiter_factory)


def create_configured_app() -> FastAPI:
    """Each spawned worker independently loads the same explicitly selected configuration."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings_path = Path(os.environ.get("EWS_NL2SQL_SETTINGS_FILE", ".local/settings.json"))
    selected_env = os.environ.get("EWS_NL2SQL_ENV_FILE")
    try:
        apply_environment_file(Path(selected_env) if selected_env else None)
        configuration = load_settings(settings_path, Path(selected_env) if selected_env else None)
    except (OSError, ValueError):
        raise ValueError("Worker configuration is invalid; values are omitted.") from None
    return create_app(configuration)
