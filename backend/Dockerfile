FROM python:3.12-slim

WORKDIR /app

# System deps (kept minimal) + Microsoft ODBC driver for SQL Server
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    unixodbc \
    unixodbc-dev \
    curl \
    gnupg \
    ca-certificates \
  && mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
     | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
  && echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
     > /etc/apt/sources.list.d/microsoft-prod.list \
  && apt-get update \
  && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY pytest.ini /app/pytest.ini
COPY tests /app/tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

