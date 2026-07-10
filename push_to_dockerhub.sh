#!/bin/bash
set -e

# echo "Logging into Docker Hub..."
# docker login

echo "Building Backend Image..."
docker build -t tamilselvan177/jobscraper-backend:latest -f Dockerfile .

echo "Building Frontend Image..."
docker build -t tamilselvan177/jobscraper-frontend:latest -f Dockerfile.frontend .

echo "Building Obscura Image (This may take a few minutes to compile Rust)..."
docker build -t tamilselvan177/jobscraper-obscura:latest -f Dockerfile.obscura .

echo "Pushing images to Docker Hub..."
docker push tamilselvan177/jobscraper-backend:latest
docker push tamilselvan177/jobscraper-frontend:latest
docker push tamilselvan177/jobscraper-obscura:latest

echo "Successfully built and pushed all images to Docker Hub!"
