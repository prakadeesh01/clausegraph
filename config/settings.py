"""Application configuration, resolved from environment variables.

Every tunable value in the service is declared here rather than read
from os.environ at the point of use. This gives each value a type and a
default, keeps the full configuration printable in one place when a
deployment misbehaves, and means a missing variable fails loudly at
startup instead of silently at first use.

Precedence, highest first: real environment variables, then a local
.env file, then the defaults below. Cloud Run injects environment
variables directly, so no .env file exists in production.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# settings.py lives in config/, so the repository root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Typed application settings with environment variable overrides."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "clausegraph"
    app_version: str = "0.1.0"
    environment: Literal["local", "ci", "production"] = "local"
    log_level: str = "INFO"

    # Cloud Run injects PORT and requires the server to bind 0.0.0.0.
    # Binding 127.0.0.1 is the single most common reason a container
    # that runs locally fails to start on Cloud Run, because the
    # platform health check cannot reach a loopback-only listener.
    host: str = "0.0.0.0"
    port: int = 8080

    # Declared now so the configuration shape stays stable as the
    # service grows. Neo4j is started by docker-compose from this block
    # onward but is not queried until the retrieval work later.
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "clausegraph-dev"

    # Optional at this stage. Made required in the block that
    # introduces the first model call, so that a missing key surfaces
    # at startup rather than mid-request.
    gemini_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance.

    Cached so the .env file is parsed once per process and so FastAPI
    dependency injection hands out the same object on every request.
    Tests clear the cache with get_settings.cache_clear() when they
    need to override the environment.

    Returns:
        The singleton Settings instance for this process.
    """
    return Settings()


if __name__ == "__main__":
    # Smoke test: print the resolved configuration so that a
    # misconfigured deployment can be diagnosed with one command.
    # The Gemini key is masked because this output ends up in logs.
    settings = get_settings()
    for field_name in settings.__class__.model_fields:
        value = getattr(settings, field_name)
        if "key" in field_name or "password" in field_name:
            value = "set" if value else "not set"
        print(f"{field_name:20} {value}")