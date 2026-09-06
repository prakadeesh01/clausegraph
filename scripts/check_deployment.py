"""Verify that a deployed ClauseGraph instance is serving correctly.

Run against any environment, local or deployed, to confirm the service
answers on the endpoints the platform and CI depend on. Kept as a
script rather than a pytest case because it targets a running remote
service rather than an in-process application.

Usage:
    python -m scripts.check_deployment https://clausegraph-xxx.run.app
    python -m scripts.check_deployment           # defaults to localhost
"""

import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

DEFAULT_BASE_URL = "http://localhost:8080"
REQUEST_TIMEOUT_S = 30


def probe(base_url: str, path: str, expected_status: int = 200) -> tuple[bool, str]:
    """Issue one GET request and report whether it met expectations.

    Args:
        base_url: Scheme and host of the service under test.
        path: Path to request, including the leading slash.
        expected_status: HTTP status treated as success.

    Returns:
        A tuple of (passed, detail) where detail is the response body on
        success or an error description on failure.
    """
    url = f"{base_url.rstrip('/')}{path}"
    start = time.perf_counter()
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_S) as response:
            body = response.read().decode("utf-8")
            elapsed = time.perf_counter() - start
            if response.status != expected_status:
                return False, f"HTTP {response.status}, expected {expected_status}"
            return True, f"{body}  ({elapsed:.2f}s)"
    except HTTPError as err:
        # Readiness deliberately returns 503 when degraded, so a
        # non-200 is only a failure when it was not the expected code.
        if err.code == expected_status:
            return True, f"HTTP {err.code} as expected"
        return False, f"HTTP {err.code}: {err.reason}"
    except (URLError, TimeoutError) as err:
        return False, f"unreachable: {err}"


def main(base_url: str) -> int:
    """Probe every endpoint the platform depends on.

    Args:
        base_url: Scheme and host of the service under test.

    Returns:
        Process exit code, 0 when every probe passed.
    """
    print(f"Checking {base_url}\n")

    checks = [
        ("/health", 200),
        ("/health/ready", 200),
        ("/openapi.json", 200),
    ]

    failures = 0
    for path, expected in checks:
        passed, detail = probe(base_url, path, expected)
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {path:20} {detail}")
        if not passed:
            failures += 1

    print()
    if failures:
        print(f"{failures} of {len(checks)} checks failed")
        return 1
    print(f"All {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    sys.exit(main(target))