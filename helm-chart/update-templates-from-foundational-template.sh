#!/bin/bash -e
######################
# Usage Note: Please use this script before re-publishing a new version of volume-autoscaler, incase there was fixes upstream
# Author: Farley <farley@neonsurge.com>
######################

# Config
export TMPFOLDER=/tmp/devops-nirvana-universal-helm-charts

# Remove previous templates
rm -f ./templates/*
rm -Rf $TMPFOLDER || true

# Clone the latest of our upstream/example/foundation repo with a "deployment" object
git clone https://github.com/DevOps-Nirvana/Universal-Kubernetes-Helm-Charts.git $TMPFOLDER

# Copy it to our repo, following symlinks with silly hacks
tar -C $TMPFOLDER/charts/deployment/templates -hcf - ./ > $TMPFOLDER/stripped.tar
tar -C ./templates -xf $TMPFOLDER/stripped.tar
# cp -L -a $TMPFOLDER/charts/deployment/templates/* ./templates/
cp -a $TMPFOLDER/charts/deployment/values.yaml ./values.yaml.upstream

# Remove cloned folder
rm -Rf $TMPFOLDER

# This is another way to do it, uses a local copy, aka not the latest "live" ones, used temporarily for debugging/development
# Disabled this by default
# cp -L -a /Users/farley/Projects/universal-kubernetes-helm-charts/charts/deployment/templates/* ./templates/

echo "Completed update from upstream template"
