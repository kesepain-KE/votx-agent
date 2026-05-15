FROM node:20-slim AS web-build

WORKDIR /web

COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app
ENV PORT=1478 \
    VOTX_HOST=0.0.0.0 \
    VOTX_MESSAGE_CONFIG=/app/message-runtime/config.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=web-build /web/dist /app/web/dist
RUN mkdir -p /app/users /app/tmp /app/message-runtime

EXPOSE 1478

ENTRYPOINT ["bash", "/app/docker-entrypoint.sh"]
