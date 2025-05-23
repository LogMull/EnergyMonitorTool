FROM python:3.11-slim

# Install dependencies
WORKDIR /app
COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
CMD ["python", "main.py"]
