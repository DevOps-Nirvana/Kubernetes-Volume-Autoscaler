# Volume Autoscaler

This helm chart is just using an import/overwrite of an [standardized Deployment helm chart](https://github.com/DevOps-Nirvana/Universal-Kubernetes-Helm-Charts/tree/master/charts/deployment)

## Introduction

This chart bootstraps a Volume Autoscaler deployment on a [Kubernetes](http://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

## Prerequisites

- [Kubernetes 1.17+ Cluster](https://kubernetes.io/releases/)
- [The kubectl binary](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [The helm 3.0+ binary](https://github.com/helm/helm/releases)
- [Prometheus](https://prometheus.io) installed on your cluster [Example 1](https://artifacthub.io/packages/helm/prometheus-community/prometheus) / [Example 2 (old)](https://github.com/helm/charts/tree/master/stable/prometheus)
- [Helm diff plugin](https://github.com/databus23/helm-diff) (optional)

## Installing the Chart

To install the chart (if you check out this codebase...)

```bash
export SERVICE_NAME="volume-autoscaler"
# Change this namespace, this should be the same namespace that Prometheus is installed in
# generally the author's "best practice" is to install all critical Kubernetes components in infrastructure
export K8S_NAMESPACE=infrastructure
# Assuming you're CLI at the project root...
export PATH_TO_HELM_CHART="./helm-chart"
# OR... If your CLI is in this folder already...
# export PATH_TO_HELM_CHART="./"

# To view a diff of what you're about to deploy (vs what you maybe already deployed)
# Note: This requires you installed the helm diff plugin (from prerequisites above)
helm diff upgrade --namespace $K8S_NAMESPACE --allow-unreleased $SERVICE_NAME $PATH_TO_HELM_CHART
# Alternatively, render out the full yaml to see and preview what is about to be deployed
helm template --namespace $K8S_NAMESPACE  $SERVICE_NAME $PATH_TO_HELM_CHART
# Optionally, diff this from above with kubectl cli
helm template --namespace $K8S_NAMESPACE  $SERVICE_NAME $PATH_TO_HELM_CHART > to_be_applied.yaml
kubectl diff -f to_be_applied.yaml
# Actually deploy/upgrade it
helm upgrade --namespace $K8S_NAMESPACE --install $SERVICE_NAME $PATH_TO_HELM_CHART
```

## Configuration

For configuration options possible, please see our [helm-charts](#todo) repository
