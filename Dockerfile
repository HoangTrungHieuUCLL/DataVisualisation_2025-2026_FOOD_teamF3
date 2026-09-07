# Runs the whole demo in one container: the Flask API on an internal port and
# the Shiny dashboard on $PORT, talking to the Postgres in DATABASE_URL.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NLTK_DATA=/usr/share/nltk_data

WORKDIR /app

# Build tools are only needed while pip compiles wheels that have no slim build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY ["app/dashboard app/requirements.txt", "./requirements.txt"]
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader -d $NLTK_DATA punkt punkt_tab \
    && apt-get purge -y build-essential && apt-get autoremove -y

COPY ["app/dashboard app/", "./dashboard/"]
COPY ["exploration/view_food_clean.csv", "./data/view_food_clean.csv"]
COPY ["start.sh", "./start.sh"]
RUN chmod +x ./start.sh

ENV FOOD_CSV_PATH=/app/data/view_food_clean.csv \
    API_PORT=5000 \
    PORT=8000

EXPOSE 8000
CMD ["./start.sh"]
