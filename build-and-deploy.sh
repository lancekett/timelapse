#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

TAG="1.0"
IMAGE_NAME="localhost/lancekett/timelapse:${TAG}"
TAR_PATH="/tmp/timelapse.tar"

# Clean up any existing image tarball to prevent Podman save errors
rm -f ${TAR_PATH}

echo "============================================="
echo "🛠️  1. Building & Saving Container Image..."
echo "============================================="
if command -v podman &> /dev/null; then
    echo "Detected Podman. Building..."
    sudo podman build -t ${IMAGE_NAME} .
    echo "Saving image to ${TAR_PATH}..."
    sudo podman save ${IMAGE_NAME} -o ${TAR_PATH}
elif command -v docker &> /dev/null; then
    echo "Detected Docker. Building..."
    docker build -t ${IMAGE_NAME} .
    echo "Saving image to ${TAR_PATH}..."
    docker save ${IMAGE_NAME} -o ${TAR_PATH}
else
    echo "❌ ERROR: Neither podman nor docker command was found."
    exit 1
fi

echo "============================================="
echo "🐳 2. Importing Image to k3s containerd..."
echo "============================================="
sudo k3s ctr -n k8s.io images import ${TAR_PATH}

echo "============================================="
echo "☸️  3. Upgrading Helm Chart..."
echo "============================================="
helm upgrade --install media-center ./helm

echo "============================================="
echo "🔄 4. Restarting Timelapse Deployment..."
echo "============================================="
kubectl rollout restart deployment/timelapse

echo "============================================="
echo "📊 5. Timelapse Pod Status (Ctrl+C to exit watch)"
echo "============================================="
kubectl get pods -l app=timelapse -w
