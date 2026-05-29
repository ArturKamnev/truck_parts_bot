FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic ./alembic
COPY alembic.ini company_knowledge.md ./

CMD ["python", "-m", "app.main"]
