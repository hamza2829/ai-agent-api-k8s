FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY migrations/ migrations/
RUN pip install --no-cache-dir . \
    && useradd --uid 10001 --create-home app
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "agent_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
