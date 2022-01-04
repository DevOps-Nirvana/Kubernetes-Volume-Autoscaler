# Kubernetes Volume Autoscaler (with Prometheus)

This repository contains a service that automatically increases the size of a Persistent Volume Claim in Kubernetes when its nearing full.  Initially engineered based on AWS EKS, this should support any Kubernetes cluster or cloud provider which supports dynamically resizing storage volumes in Kubernetes.


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

### Installation with Helm

Now that your cluster has a `StorageClass` which supports expansion, you can install the Volume Autoscaler

```bash
# First, setup this repo for your helm
helm repo add devops-nirvana https://devops-nirvana.s3.amazonaws.com/helm-charts/

# Example Install 1 - Using autodiscovery, must be in the same namespace as Prometheus
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE

# Example 2 - Manually setting where Prometheus is
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace ANYWHERE_DOESNT_MATTER \
  --set "prometheus_url=http://prometheus-server.namespace.svc.cluster.local"

# Example 3 - Recommended usage, automatically detect Prometheus and use slack notifications
helm upgrade --install volume-autoscaler devops-nirvana/volume-autoscaler \
  --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE \
  --set "slack_webhook_url=https://hooks.slack.com/services/123123123/4564564564/789789789789789789" \
  --set "slack_channel=my-slack-channel-name"
```

#### Advanced helm usage...
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


### (Alternate) Installation with `kubectl`

```bash
# This simple installation will work as long as you put this in the same namespace as Prometheus
# The default namespace of this yaml is hardcoded to is `infrastructure`.  If you'd like to change
# the namespace you can run the first few commands below...

# IF YOU USE `infrastructure` AS THE NAMESPACE FOR PROMETHEUS SIMPLY...
kubectl --namespace infrastructure apply https://devops-nirvana.s3.amazonaws.com/volume-autoscaler/volume-autoscaler-1.0.1.yaml

# OR, IF YOU NEED TO CHANGE THE NAMESPACE...
# #1: Download the yaml...
wget https://devops-nirvana.s3.amazonaws.com/volume-autoscaler/volume-autoscaler-1.0.1.yaml
# #1: Or download with curl
curl https://devops-nirvana.s3.amazonaws.com/volume-autoscaler/volume-autoscaler-1.0.1.yaml -o volume-autoscaler-1.0.1.yaml
# #2: Then replace the namespace in this, replacing
cat volume-autoscaler-1.0.1.yaml | sed 's/"infrastructure"/"PROMETHEUS_NAMESPACE_HERE"/g' > ./to_be_applied.yaml
# #3: If you wish to have slack notifications, edit this to_be_applied.yaml and embed your webhook on the value: line for SLACK_WEBHOOK and set the SLACK_CHANNEL as well accordingly
# #4: Finally, apply it...
kubectl --namespace REPLACEME_WITH_PROMETHEUS_NAMESPACE apply ./to_be_applied.yaml
```

### Validation

To confirm the volume autoscaler is working properly this repo has an example which you can apply to your Kubernetes cluster which is an PVC and a pod which uses that PVC and fills the disk up constantly.  To do this...

```bash
# Simply run this on your terminal
kubectl apply -f https://raw.githubusercontent.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/master/examples/simple-pod-with-pvc.yaml
```
Then if you'd like to follow-along, "follow" the logs of your volume autoscaler to watch it detect full disk and scale up.


# TODO

This todo list is mostly for the Author(s), but any contributions are also welcome.  Please [submit an Issue](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/issues) for issues or requests, or an [Pull Request](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler/pulls) if you added some code.

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
