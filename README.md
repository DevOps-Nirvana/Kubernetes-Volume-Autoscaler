# Kubernetes Volume Autoscaler (using Prometheus)

<a href="https://hub.docker.com/r/devopsnirvana/kubernetes-volume-autoscaler"><img src="https://img.shields.io/docker/pulls/devopsnirvana/kubernetes-volume-autoscaler?style=plastic" alt="Docker Hub Pulls"></a> <a href="https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/releases/tag/1.0.2"><img src="https://img.shields.io/docker/v/devopsnirvana/kubernetes-volume-autoscaler/1.0.2?label=Latest%20Release&style=plastic" alt="Latest Release"></a> <a href="https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/stargazers"><img src="https://img.shields.io/github/stars/DevOps-Nirvana/Kubernetes-Volume-Autoscaler?style=social" alt="Stargazers on Github"></a>

This repository contains a [Kubernetes controller](https://kubernetes.io/docs/concepts/architecture/controller/) that automatically increases the size of a Persistent Volume Claim in Kubernetes when it is nearing full.  Initially engineered based on AWS EKS, this should support any Kubernetes cluster or cloud provider which supports dynamically hot-resizing storage volumes in Kubernetes.

Keeping your volumes at a minimal size can help reduce cost, but having to manually scale them up can be painful and a waste of time for an DevOps / Systems Administrator.  This is often used on storage volumes against things in Kubernetes such as [Prometheus](https://prometheus.io), [MySQL](https://artifacthub.io/packages/helm/bitnami/mysql), [Redis](https://artifacthub.io/packages/helm/bitnami/redis), etc.


## Requirements

- [Kubernetes 1.17+ Cluster](https://kubernetes.io/releases/)
- [kubectl binary](https://kubernetes.io/docs/tasks/tools/#kubectl) installed and setup with your cluster
- [The helm 3.0+ binary](https://github.com/helm/helm/releases)
- [Prometheus](https://prometheus.io) installed on your cluster [Example 1](https://artifacthub.io/packages/helm/prometheus-community/prometheus) / [Example 2 (old)](https://github.com/helm/charts/tree/master/stable/prometheus)
- Using an Storage Class with `allowVolumeExpansion == true`
- Using an Volume provisioner which supports dynamic volume expansion
  - EKS default driver on 1.17+ does
  - [AWS EBS CSI driver](https://github.com/kubernetes-sigs/aws-ebs-csi-driver) also does


## Prerequisites

As mentioned above, you must have a storageclass which supports volume expansion, and the provisioner you're using must also support volume expansion.  Ideally, "hot"-volume expansion so your services never have to restart.  AWS EKS built-in provisioner `kubernetes.io/aws-ebs` supports this, and so does the `efs.csi.aws.com` CSI driver.  To check/enable this...

```bash
# First, check if your storage class supports volume expansion...
$ kubectl get storageclasses
NAME                   PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
standard               kubernetes.io/aws-ebs   Delete          Immediate              false                  10d

# If ALLOWVOLUMEEXPANSION is not set to true, patch it to enable this
kubectl patch storageclass standard -p '{"allowVolumeExpansion": true}'
```

**NOTE:** The above storageclass comes with EKS, however, it only supports gp2, which is largely a deprecated and much slower storage driver than [gp3](https://aws.amazon.com/about-aws/whats-new/2020/12/introducing-new-amazon-ebs-general-purpose-volumes-gp3/).  I HIHGLY recommend before using EKS you install the [AWS EBS CSI driver](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html) to gain [gp3](https://aws.amazon.com/about-aws/whats-new/2020/12/introducing-new-amazon-ebs-general-purpose-volumes-gp3/) support and more future-proof support of Amazon's various storage volumes and their lifecycles.

If you do this, you can/should completely remove GP2 support, and after installing the above CSI driver, create a storageclass with the new driver with best-practices in it by default including...

- Retain-ing the volume if it was deleted (to prevent accidental data loss)
- Having all disks encrypted-at-rest by default, for compliance/security
- Using gp3 by default for faster disk bandwidth and IO

```bash
# For this, simply delete your old default StorageClass
kubectl delete storageclass standard
# Then apply/create a new default gp3 using the AWS EBS CSI driver you installed
kubectl apply -f https://raw.githubusercontent.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/master/examples/gp3-default-encrypt-retain-allowExpansion-storageclass.yaml
```

## Installation with Helm

Now that your cluster has a `StorageClass` which supports expansion, you can install the Volume Autoscaler

```bash
# First, setup this repo for your helm
helm repo add devops-nirvana https://devops-nirvana.s3.amazonaws.com/helm-charts/

# Example Pre-Install - DRY RUN + VERBOSE, Using auto-discovery, must be in the same namespace as Prometheus
#   Do this if you want to see what this script "would" do.  To view it, view the logs of this service after you deploy it
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE \
  --set "dry_run=true" \
  --set "verbose=true"

# Example Install 1 - Using auto-discovery, must be in the same namespace as Prometheus
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE

# Example 2 - Manually setting where Prometheus is
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace ANYWHERE_DOESNT_MATTER \
  --set "prometheus_url=http://prometheus-server.namespace.svc.cluster.local"

# Example 3 - Recommended final usage, auto-discovery and use slack notifications.  NOTE: Check helm-chart/values.yml for other variables you can override globally
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE \
  --set "slack_webhook_url=https://hooks.slack.com/services/123123123/4564564564/789789789789789789" \
  --set "slack_channel=my-slack-channel-name"
```

There are also various other variables you're able to set as easily as above.  Please see: [values.yaml](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/blob/master/helm-chart/values.yaml#L9) for all the simple values to adjust this service.  In addition, review the rest of that file if you'd like to adjust other things (like resource limits, node selectors, taints/tolerances, adding labels, etc).

### Advanced helm usage...
```bash
# To update your local knowledge of remote repos, you may need to do this before upgrading...
helm repo update

# To view what changes it will make, if you change things, this requires the helm diff plugin - https://github.com/databus23/helm-diff
helm diff upgrade volume-autoscaler --allow-unreleased devops-nirvana/volume-autoscaler \
  --namespace infrastructure \
  --set "slack_webhook_url=https://hooks.slack.com/services/123123123/4564564564/789789789789789789" \
  --set "slack_channel=my-slack-channel-name" \
  --set "prometheus_url=http://prometheus-server.infrastructure.svc.cluster.local"

# To remove the service, simply run...
helm uninstall volume-autoscaler
```


## (Alternate) Installation with `kubectl`

```bash
# This simple installation will work as long as you put this in the same namespace as Prometheus
# The default namespace of this yaml is hardcoded to is `infrastructure`.  If you'd like to change
# the namespace you can run the first few commands below...

# IF YOU USE `infrastructure` AS THE NAMESPACE FOR PROMETHEUS SIMPLY...
kubectl --namespace infrastructure apply https://devops-nirvana.s3.amazonaws.com/volume-autoscaler/volume-autoscaler-1.0.2.yaml

# OR, IF YOU NEED TO CHANGE THE NAMESPACE...
# #1: Download the yaml...
wget https://devops-nirvana.s3.amazonaws.com/volume-autoscaler/volume-autoscaler-1.0.2.yaml
# #1: Or download with curl
curl https://devops-nirvana.s3.amazonaws.com/volume-autoscaler/volume-autoscaler-1.0.2.yaml -o volume-autoscaler-1.0.2.yaml
# #2: Then replace the namespace in this, replacing
cat volume-autoscaler-1.0.2.yaml | sed 's/"infrastructure"/"PROMETHEUS_NAMESPACE_HERE"/g' > ./to_be_applied.yaml
# #3: If you wish to have slack notifications, edit this to_be_applied.yaml and embed your webhook on the value: line for SLACK_WEBHOOK and set the SLACK_CHANNEL as well accordingly
# #4: Finally, apply it...
kubectl --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE apply ./to_be_applied.yaml
```

## Validation

To confirm the volume autoscaler is working properly this repo has an example which you can apply to your Kubernetes cluster which is an PVC and a pod which uses that PVC and fills the disk up constantly.  To do this...

```bash
# Simply run this on your terminal
kubectl apply -f https://raw.githubusercontent.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/master/examples/simple-pod-with-pvc.yaml
# Then if you'd like to follow-along, "follow" the logs of your volume autoscaler pod to watch it detect full disk and scale up.
kubectl get pods | grep -i volume-autoscaler
kubectl logs --since=10m --follow volume-autoscaler-pod-goes-here-from-the-above-command-output
```

## Per-Volume Configuration / Annotations

This controller also supports tweaking your volume-autoscaler configuration per-PVC with annotations.  The annotations supported are...

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sample-volume-claim
  annotations:
    # This is when we want to scale up after the disk is this percentage (out of 100) full
    volume.autoscaler.kubernetes.io/scale-above-percent: "80"   # 80 is the default value
    # This is how many intervals must go by above the scale-above-percent before triggering an autoscale action
    volume.autoscaler.kubernetes.io/scale-after-intervals: "5"  # 5 is this default value
    # This is how much to scale a disk up by, in percentage of the current size.
    #   Eg: If this is set to "10" and the disk is 100GB, it will scale to 110GB
    #   At larger disk sizes you may want to set this on your PVCs to like "5" or "10"
    volume.autoscaler.kubernetes.io/scale-up-percent: "50"      # 50 (percent) is the default value
    # This is the smallest increment to scale up by.  This helps when the disks are very small, and helps hit the minimum increment value per-provider (this is 1GB on AWS)
    volume.autoscaler.kubernetes.io/scale-up-min-increment: "1000000000"  # 1GB by default (in bytes)
    # This is the maximum increment to scale up by.  This helps when the disks are very LARGE, to prevent them from growing too much at a time.
    #   This can be used instead of or in addition to scale-up-percent
    volume.autoscaler.kubernetes.io/scale-up-max-increment: ""  # Unset by default(in "bytes")
    # This is the largest disk size ever allowed for this tool to scale up to.  This is set to 16TB by default, because that's the limit of AWS EBS
    volume.autoscaler.kubernetes.io/scale-up-max-size: "16000000000000"  # 16TB by default (in bytes)
    # How long (in seconds) we must wait before scaling this volume again.  For AWS EBS, this is 6 hours which is 21600 seconds but for good measure we add an extra 10 minutes to this, so 22200
    volume.autoscaler.kubernetes.io/scale-cooldown-time: "22200"  
    # If you want the autoscaler to completely ignore/skip this PVC, set this to "true"
    volume.autoscaler.kubernetes.io/ignore: "false"  
    # Finally, Do not set this, and if you see this ignore this, this is how Volume Autoscaler keeps its "state"
    volume.autoscaler.kubernetes.io/last-resized-at: "123123123"  # This will be an Unix epoch timestamp
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
```

# Release History
### [Release: 1.0.3 - Jan 23, 2022](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/releases/tag/1.0.3)
```
Handle signal from Kubernetes to kill/restart properly/quickly
```

### [Release: 1.0.2 - Jan 15, 2022](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/releases/tag/1.0.2)
```
Automatically detecting version of Prometheus and using newer functions to de-bounce invalid PVCs automatically
Adding max-increment annotation/variable support
Adding exception handling in our main loop to handle jitter nicely and not fail catastrophically if someone has bad PVC annotations
Making all variables settable by a value in the helm chart
Adding verbose support, which when enabled prints out full data from the objects detected, and prints out even non-alerting disks
Printing the number of PVCs found in the log, useful when not in verbose mode
```

### [Release: 1.0.1 - Jan 4, 2022](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/releases/tag/1.0.1)
```
Initial Public Release
Basic PVC Annotation support
Publishing a Helm Chart
A few variables configurable in the Helm Chart values
Some basic documentation and installation help/guides
```

# TODO

Current Release: 1.0.2

This todo list is mostly for the Author(s), but any contributions are also welcome.  Please [submit an Issue](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/issues) for issues or requests, or an [Pull Request](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/pulls) if you added some code.

* Add full helm chart values documentation markdown table
* Push to helm repo in a Github Action and push the static yaml as well
* Add tests coverage to ensure the software works as intended moving forward
* Do some load testing to see how well this software deals with scale, document how much resources needed for each interval.  (10 PVCs, 100+ PVC, 500 PVC)
* Generate kubernetes EVENTS when we resize volumes so everyone knows we are doing things, to be a good controller
* Add badges to the README regarding Github Actions success/failures
* Listen/watch to events of the PV/PVC, or listen/read from Prometheus to monitor and ensure the resizing happens, log and/or slack it accordingly
* Test it and add working examples of using this on other cloud providers (Azure / Google Cloud)
* Make per-PVC annotations to (re)direct Slack to different webhooks and/or different channel(s)
* Discuss what the ideal "default" amount of time before scaling.  Currently is 5 minutes (5, 60 minute intervals)
* Discuss what the ideal "default" scale up size is, currently 50%.  Suggestion has been made to lower this to around 20%

# Notes for Development

This tool can easily be run locally, as long as you have an functioning kubectl config, and as long as you can reach the http(s) endpoint for your cluster's prometheus.  If your prometheus is internal-only, you may need to have an VPN setup into your VPC/Cluster.  I recommend OpenVPN if you're installing one in your Kubernetes cluster.  I have an [example of installing OpenVPN into Kubernetes here](#todo).

```bash
# To test out/develop new features, first get your prometheus IP address...
kubectl get services --all-namespaces | grep -i prometheus-server
infrastructure  prometheus-server  ClusterIP  10.100.57.102  <none>  80/TCP  109d
# Then take its IP address and check if you can use it...
curl http://10.100.57.102
<a href="/graph">Found</a>
# Alternatively, if your ops/devops person setup an ingress to make this accessible externally...
curl https://prometheus.mycompany.com
# Once you have established a functioning URL to prometheus, put it in the following command
# and you'll be off and running in a safe way that won't affect anything because of DryRun
VERBOSE=true SCALE_AFTER_INTERVALS=1 DRY_RUN=true PROMETHEUS_URL=http://10.100.57.102 ./main.py
```
