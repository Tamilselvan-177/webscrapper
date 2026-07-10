#!/bin/bash
set -e

echo "Pulling latest images from Docker Hub..."
docker compose pull

echo "Starting the application..."
docker compose up -d --build

echo "Deployment successful! 🚀"
