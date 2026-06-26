FROM python:3.12-slim

# Faster, quieter, no .pyc clutter.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy the full project first so the editable install can discover the `app`
# package (flat layout). All runtime deps ship manylinux wheels for cp312
# (psycopg[binary], cryptography, argon2-cffi), so no system build tools needed.
COPY . .
RUN pip install --upgrade pip && pip install -e .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
