FROM node:20-slim AS web-build

WORKDIR /web

COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=web-build /web/dist /app/web/dist

EXPOSE 1478

ENTRYPOINT ["bash", "/app/docker-entrypoint.sh"]
