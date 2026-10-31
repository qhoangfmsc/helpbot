FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY helpbot ./helpbot
COPY main.py .
RUN useradd --create-home app && chown -R app /app
USER app

# One run: scrape -> delta -> upload, then exit (0 on success). Needs GEMINI_API_KEY in the environment.
CMD ["python", "main.py"]
