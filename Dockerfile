# Kozquloq audit compute: runs `kozquloq scan` + `export`
# against a dataset mounted at /data and writes results to /out.
#
# Build:  docker build -t kozquloq .
# Local:  docker run -v $PWD/v1.0-mini:/data/v1.0-mini -v $PWD/out:/out kozquloq \
#           scan --dataroot /data --db /out/kozquloq.duckdb
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
COPY scripts ./scripts

RUN uv sync --frozen --no-dev --no-install-workspace && uv pip list >/dev/null

ENTRYPOINT ["uv", "run", "--no-sync", "kozquloq"]
