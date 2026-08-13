# ClauseGraph

Multi-agent contract risk analysis with hybrid retrieval over UK legislation.

Status: in development.

## What this is

Takes a commercial contract, extracts its clauses, classifies each for
risk, cross-references flagged clauses against UK legislation using
hybrid dense and sparse retrieval, maps clause dependencies in Neo4j,
pauses for human review of high-risk findings, and produces a cited
risk report.

Evaluated against expert annotations from the Contract Understanding
Atticus Dataset (CUAD, CC BY 4.0) rather than self-generated labels.

## Stack

LangGraph · FastAPI · Neo4j · FAISS + BM25 + CrossEncoder · Gemini ·
Docker · GitHub Actions · GCP Cloud Run · pytest

## Quick start

```bash
git clone https://github.com/prakadeesh01/clausegraph.git
cd clausegraph

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS or Linux

pip install -e ".[dev]"
cp .env.example .env            # then fill in GEMINI_API_KEY
pytest
```

Run the full stack, including Neo4j:

```bash
docker compose up --build
curl http://localhost:8080/health
curl http://localhost:8080/health/ready
```

The Neo4j browser is at http://localhost:7474 (neo4j / clausegraph-dev).

## Technical Q&A

Written as each decision is made rather than reconstructed at the end.

### Why are liveness and readiness separate endpoints?

They answer different questions and a platform reacts to each
differently. A liveness failure restarts the container; a readiness
failure only withholds traffic. If a single endpoint checked Neo4j,
a brief database outage would be read as a broken process and the
container would be killed and restarted into the same outage. Splitting
them means liveness stays green while readiness returns 503, so traffic
is withheld from a container that keeps running with its indexes still
warm in memory. Cloud Run has no separate readiness probe, so there
`/health/ready` serves as the operational diagnostic and the design
ports unchanged to Kubernetes.

### Why does the server bind 0.0.0.0 rather than 127.0.0.1?

`127.0.0.1` accepts connections only from inside the container. Cloud
Run's health check arrives from outside, finds nothing listening, and
terminates the instance — while `docker exec` plus `curl localhost`
inside the same container returns 200. That asymmetry makes it the most
confusing common deployment failure, so the bind address is a named
setting with an explanatory comment rather than a literal in the
startup command.

### Why declare dependency ranges in pyproject.toml but install from requirements.lock.txt?

Ranges keep local upgrades easy; exact pins keep image builds
reproducible. The lock file is generated after installing runtime
dependencies only and before dev extras, so pytest and ruff never reach
the production image. The two common failure modes are a `pip freeze`
of the entire environment used as the declared dependency list, and a
declared list with no versions at all — the first cannot be upgraded,
the second cannot be reproduced.

### Why is the Dockerfile multi-stage?

Image layers are additive: a file removed in a later layer still ships
in the earlier one, so build tooling cannot be installed and then
cleaned up. The builder stage creates the virtual environment and the
runtime stage starts from a clean base and copies only `/opt/venv`
across. Dependencies are also copied and installed before application
source, so a code change reuses the cached install layer — a rebuild
after editing one Python file takes seconds rather than a minute.

### Why is CMD in shell form with an explicit exec?

Cloud Run injects `PORT` at runtime, and exec-form `CMD` performs no
variable expansion — uvicorn would receive the literal string
`${PORT:-8080}` and fail to bind. Shell form expands it, but leaves
`sh` as PID 1, so SIGTERM never reaches uvicorn and the lifespan
shutdown hook never runs. Prefixing with `exec` replaces the shell
process with uvicorn, giving expansion and PID 1 together. Verified by
the process ID moving from 7 to 1 and the shutdown log appearing.

### Why does the API wait on a Neo4j query rather than a port check?

Neo4j opens port 7687 seconds before it can serve queries, while it is
still loading stores. A port check reports healthy too early and the
first connection fails. The compose healthcheck runs `RETURN 1` through
`cypher-shell`, and `depends_on: condition: service_healthy` gates API
startup on it, which replaces a fixed `sleep` that is either too short
or wasteful.

### Why load resources in the lifespan hook rather than per request?

The FAISS index, BM25 corpus, Neo4j driver and CrossEncoder are
expensive to construct and identical across requests. FastAPI's
`lifespan` runs once per process, so they are built at startup and
shared. Rebuilding retrieval structures inside the request handler is
the specific mistake that makes a working demo unusable as a service.

## Licence

MIT. CUAD is used under CC BY 4.0.