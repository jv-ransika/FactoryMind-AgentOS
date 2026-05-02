FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md CHANGELOG.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN useradd -m agentos
USER agentos

EXPOSE 8000

CMD ["agent-os", "serve", "--host", "0.0.0.0", "--port", "8000", "--root", "/data/.agent-os", "--runtime", "local"]
