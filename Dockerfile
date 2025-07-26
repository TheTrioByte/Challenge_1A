FROM --platform=linux/amd64 python:3.9-slim

COPY . /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x entrypoint.sh
ENTRYPOINT ["python", "extract_outline.py", "/app/input", "/app/output"]

