FROM python:3.12-slim

WORKDIR /app

COPY package*.json ./
# Build dependencies needed for sqlite3 native module
RUN apk add --no-cache python3 make g++ sqlite && \
    npm install --production

COPY app ./app

EXPOSE 8081

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
