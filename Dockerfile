FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scenarios ./scenarios
COPY LICENSE readme.md ux.png ./

RUN useradd --create-home --uid 10001 cyberops \
    && chown -R cyberops:cyberops /app

USER cyberops

EXPOSE 8090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
