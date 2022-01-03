# Kubernetes Volume Autoscaler (with Prometheus)

This repository contains a service that automatically adjusts the size of a Persistent Volume Claim in Kubernetes.  Initially engineered based on AWS EKS, this should support any Kubernetes cluster or cloud provider which supports dynamically resizing volumes in Kubernetes.


# Requirements

- [Kubernetes 1.17+ Cluster](https://kubernetes.io/releases/)
- [kubectl binary](https://kubernetes.io/docs/tasks/tools/#kubectl) installed and setup with your cluster
- [The helm 3.0+ binary](https://github.com/helm/helm/releases)
- [Prometheus](https://prometheus.io) installed on your cluster [Example 1](https://artifacthub.io/packages/helm/prometheus-community/prometheus) / [Example 2 (old)](https://github.com/helm/charts/tree/master/stable/prometheus)


# TODO

* Add tests coverage to ensure the software works as intended moving forward
* Do some load testing to see how well this software deals with scale (100+ PVs, 500+ PVs, etc)
* Figure out what type of Memory/CPU is necessary for 500+ PVs, see above
* Add more documentation / diagramming
* Add simple example of how to install this in Kubernetes cluster with Helm
* Add simple example of how to install this in Kubernetes cluster with an simple `kubectl apply`
* Add verbosity levels for print statements, to be able to quiet things down in the logs
* Make Slack alert on resize happening or on resizing failing for some reason
* Push to helm repo in a Github Action
* Generate kubernetes EVENTS (add to rbac) so everyone knows we are doing things, to be a good controller
* Add badges to the README
* Listen/watch to events of the PV/PVC to monitor and ensure the resizing happens, log it accordingly
* Test it and add working examples of using this on other cloud providers (Azure / Google Cloud)
* Make per-PVC annotations to (re)direct Slack to different webhooks and/or different channel(s)
* Discuss what the ideal "default" amount of time before scaling.  Currently is 5 minutes (5, 60 minute intervals)
