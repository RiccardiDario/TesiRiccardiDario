FROM python:3.9-slim
RUN pip install --no-cache-dir flask
WORKDIR /app
COPY app.py /app/
CMD ["python", "app.py"]