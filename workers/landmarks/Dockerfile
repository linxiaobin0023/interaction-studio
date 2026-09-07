FROM python:3.12-slim

WORKDIR /worker
COPY workers/landmarks/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY workers/landmarks/analyze.py ./analyze.py

ENTRYPOINT ["python", "analyze.py"]
