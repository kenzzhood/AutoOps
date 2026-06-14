FROM python:3.11-slim
WORKDIR /app
COPY shared/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY shared /app/shared
COPY services/api_gateway/main.py /app/main.py
ENV PYTHONPATH=/app/shared
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
