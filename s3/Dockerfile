# One-shot setup of the Garage node; boto3 only for moving the frames on disk.
FROM python:3.12-slim

RUN pip install --no-cache-dir boto3==1.44.9

WORKDIR /app
COPY setup_garage.py ./

USER 10001

ENTRYPOINT ["python", "setup_garage.py"]
