FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CODEX_HOME=/root/.codex

RUN apt-get update && apt-get install -y --no-install-recommends \
    iverilog \
    nodejs \
    npm \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @openai/codex

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /workspace

CMD ["python", "run_simulation.py", "--check-only"]
