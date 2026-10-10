#!/usr/bin/env bash
# One-time setup: kind cluster + Online Boutique + Chaos Mesh.
# Prereqs: docker, kind, kubectl, helm, python3.
set -euo pipefail

pip install -r requirements.txt

kind create cluster --name chaos

[ -d microservices-demo ] || git clone --depth 1 https://github.com/GoogleCloudPlatform/microservices-demo
kubectl apply -f microservices-demo/release/kubernetes-manifests.yaml
kubectl wait --for=condition=available deployment --all --timeout=600s

helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
kubectl create ns chaos-mesh --dry-run=client -o yaml | kubectl apply -f -
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
kubectl -n chaos-mesh wait --for=condition=ready pod --all --timeout=300s

cat <<MSG

Setup complete. In a SEPARATE terminal, leave this running:
    kubectl port-forward deployment/frontend 8080:8080
Then run:  ./demo.sh
MSG
