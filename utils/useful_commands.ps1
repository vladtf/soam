# Useful commands for development and deployment

## rebuild frontend image
docker compose build frontend
docker compose up -d --no-deps frontend

## rebuild backend image
docker compose build backend
docker compose up -d --no-deps backend

