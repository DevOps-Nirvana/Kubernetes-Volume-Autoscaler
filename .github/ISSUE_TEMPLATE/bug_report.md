---
name: Bug report
about: Create a report to help us fix a flaw you are experiencing
title: ''
labels: bug
assignees: AndrewFarley

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior
1. Step 1
1. Step 2
1. Step 3

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Extra Information Requested**
 - Kubernetes Version: 1.21 (example)
 - Prometheus Version: 2.39.1 (example
 - Enable "Verbose" mode in helm chart, and copy/paste the values printed therein
```
Volume infrastructure.prometheus-server is 62% in-use of the 10Gi available
  VERBOSE DETAILS:
    name: prometheus-server
    volume_size_spec: 10Gi
    volume_size_spec_bytes: 10737418240
    volume_size_status: 10Gi
    volume_size_status_bytes: 10737418240
    namespace: infrastructure
    storage_class: gp3-retain
    resource_version: 8498015
    uid: bfc7827c-56ac-4bdf-b79e-06090e400294
    last_resized_at: 0
    scale_above_percent: 80
    scale_after_intervals: 5
    scale_up_percent: 20
    scale_up_min_increment: 1000000000
    scale_up_max_increment: 16000000000000
    scale_up_max_size: 16000000000000
    scale_cooldown_time: 22200
    ignore: False
 and is not above 80%
```
