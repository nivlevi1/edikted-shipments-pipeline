FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY download.py ingest.py ./
RUN mkdir -p /app/src
CMD ["sh", "-c", "python download.py && python ingest.py"]
