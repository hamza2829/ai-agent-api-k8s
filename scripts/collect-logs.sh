#!/usr/bin/env bash
# Do not print Secret values or complete container environments.
set -u
mkdir -p artifacts/cluster
kubectl version -o yaml > artifacts/cluster/version.yaml 2>&1 || true
kubectl get pods,deployments,services,jobs -n agent-demo -o wide > artifacts/cluster/resources.txt 2>&1 || true
kubectl get events -n agent-demo --sort-by=.metadata.creationTimestamp > artifacts/cluster/events.txt 2>&1 || true
kubectl describe pods -n agent-demo > artifacts/cluster/pods.txt 2>&1 || true
while IFS= read -r pod; do
  safe_name="${pod#pod/}"
  kubectl logs -n agent-demo "$pod" --all-containers=true --prefix > "artifacts/cluster/${safe_name}.log" 2>&1 || true
  kubectl logs -n agent-demo "$pod" --all-containers=true --prefix --previous > "artifacts/cluster/${safe_name}-previous.log" 2>&1 || true
done < <(kubectl get pods -n agent-demo -o name 2>/dev/null)
