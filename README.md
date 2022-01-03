# Kubernetes Volume Autoscaler (with Prometheus)

This repository contains a service that automatically increases the size of a Persistent Volume Claim in Kubernetes when its nearing full.  Initially engineered based on AWS EKS, this should support any Kubernetes cluster or cloud provider which supports dynamically resizing storage volumes in Kubernetes.


## Requirements

- [Kubernetes 1.17+ Cluster](https://kubernetes.io/releases/)
- [kubectl binary](https://kubernetes.io/docs/tasks/tools/#kubectl) installed and setup with your cluster
- [The helm 3.0+ binary](https://github.com/helm/helm/releases)
- [Prometheus](https://prometheus.io) installed on your cluster [Example 1](https://artifacthub.io/packages/helm/prometheus-community/prometheus) / [Example 2 (old)](https://github.com/helm/charts/tree/master/stable/prometheus)


### Installation with Helm

```bash
$ helm repo add devops-nirvana https://devops-nirvana.s3.amazonaws.com/helm-charts/

# Example 1 - Using autodiscovery, must be in the same namespace as Prometheus
$ helm install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE

# Example 2 - Manually setting where Prometheus is
$ helm install volume-autoscaler devops-nirvana/volume-autoscaler \
  --set "prometheus_url=http://prometheus-server.namespace.svc.cluster.local"

# Example 3 - Full Example, manually setting where Prometheus is and having slack notifications
$ helm install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace NAMESPACE_FOR_VOLUME_AUTOSCALER \
  --set "slack_webhook_url=https://hooks.slack.com/services/123123123/4564564564/789789789789789789" \
  --set "slack_channel=my-slack-channel-name" \
  --set "prometheus_url=http://prometheus-server.namespace.svc.cluster.local"
```

Advanced helm usage...
```bash
# To view what changes it will make, if you change things, this requires the helm diff plugin - https://github.com/databus23/helm-diff
helm diff upgrade volume-autoscaler --allow-unreleased devops-nirvana/volume-autoscaler \
  --namespace infrastructure \
  --set "slack_webhook_url=https://hooks.slack.com/services/123123123/4564564564/789789789789789789" \
  --set "slack_channel=my-slack-channel-name" \
  --set "prometheus_url=http://prometheus-server.namespace.svc.cluster.local"

# To remove the service, simply run...
helm uninstall volume-autoscaler
```


### Installation with `kubectl`

```bash
# Simple example, as long as you put this in the same namespace as Prometheus it will work
# The default namespace this yaml is hardcoded to is `infrastructure`.  If you'd like to change
# the namespace you can run the first few commands below...

# IF YOU USE `infrastructure` AS THE NAMESPACE FOR PROMETHEUS SIMPLY...
# NOTE: Slack notification will not work if you simply use this, you'll need to download this and customize the YAML to add your Slack Webhook
$ kubectl --namespace infrastructure apply https://devops-nirvana.s3.amazonaws.com/helm-charts/volume-autoscaler-1.0.1.yaml

# OR, IF YOU NEED TO CHANGE THE NAMESPACE...
# #1: Download the yaml...
$ wget https://devops-nirvana.s3.amazonaws.com/helm-charts/volume-autoscaler-1.0.1.yaml
# #1: Or download with curl
$ curl https://devops-nirvana.s3.amazonaws.com/helm-charts/volume-autoscaler-1.0.1.yaml -o volume-autoscaler-1.0.1.yaml
# #2: Then replace the namespace in this, replacing
cat volume-autoscaler-1.0.1.yaml | sed 's/"infrastructure"/"PROMETHEUS_NAMESPACE_HERE"/g' > ./to_be_applied.yaml
# #3: If you wish to have slack notifications, edit this to_be_applied.yaml and embed your webhook on the value: line for SLACK_WEBHOOK
# #4: Finally, apply it...
$ kubectl --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE apply ./to_be_applied.yaml
```


# TODO

* Push to helm repo in a Github Action and push the static yaml as well
* Add tests coverage to ensure the software works as intended moving forward
* Do some load testing to see how well this software deals with scale (100+ PVs, 500+ PVs, etc)
* Figure out what type of Memory/CPU is necessary for 500+ PVs, see above
* Add verbosity levels for print statements, to be able to quiet things down in the logs
* Generate kubernetes EVENTS (add to rbac) so everyone knows we are doing things, to be a good controller
* Add badges to the README
* Listen/watch to events of the PV/PVC to monitor and ensure the resizing happens, log and/or slack it accordingly
* Test it and add working examples of using this on other cloud providers (Azure / Google Cloud)
* Make per-PVC annotations to (re)direct Slack to different webhooks and/or different channel(s)
* Discuss what the ideal "default" amount of time before scaling.  Currently is 5 minutes (5, 60 minute intervals)
