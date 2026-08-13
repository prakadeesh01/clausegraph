"""Liveness and readiness endpoints.

Two endpoints rather than one, because they answer different questions
and a platform reacts to them differently.

/health is liveness: is this process alive at all? It touches no
dependency and must stay fast and unconditional, because a failure here
means the container gets restarted.

/health/ready is readiness: can this process serve real traffic? It
checks every downstream dependency and returns 503 when any of them is
unavailable, which takes the instance out of the load balancer without
killing it.

The dependency checks are empty in this block. The contract is defined
now so that later blocks add entries to one dictionary rather than
reshaping the response.
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from config.settings import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    """Payload returned by the liveness probe."""

    status: str = Field(description="Always 'ok' when the process is running.")
    service: str = Field(description="Application name.")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Deployment environment.")


class ReadinessResponse(BaseModel):
    """Payload returned by the readiness probe."""

    status: str = Field(description="'ready' if all checks pass, else 'degraded'.")
    checks: dict[str, bool] = Field(
        description="One entry per downstream dependency, True when reachable."
    )


def _run_dependency_checks(settings: Settings) -> dict[str, bool]:
    """Probe every downstream dependency the service needs to serve traffic.

    Args:
        settings: Resolved application settings.

    Returns:
        A mapping of dependency name to reachability. Empty while the
        service has no downstream dependencies, which readiness treats
        as ready rather than as a failure.
    """
    checks: dict[str, bool] = {}
    # Neo4j, the vector index and the Gemini client are registered here
    # as the blocks that introduce them land.
    return checks


@router.get("", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Report that the process is alive.

    Deliberately does no dependency work. A slow or failing liveness
    probe causes the platform to restart a container that may be
    perfectly healthy but waiting on something else.

    Returns:
        Service identity and the environment it believes it is in.
    """
    settings = get_settings()
    return LivenessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness(response: Response) -> ReadinessResponse:
    """Report whether every downstream dependency is reachable.

    Args:
        response: Injected so the status code can be set to 503 without
            raising, which keeps the diagnostic body in the reply.

    Returns:
        Overall status plus the per-dependency check results. Sets HTTP
        503 when any check fails, so an orchestrator can withhold
        traffic while still reading which dependency is at fault.
    """
    checks = _run_dependency_checks(get_settings())
    all_ready = all(checks.values())

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if all_ready else "degraded",
        checks=checks,
    )