#!/usr/bin/env bash

## Sets any necessary pre-requisite folders and builds/pulls docker images.
## Uses the local repository as priority over published docker images.

# Pull docker images from online where available
docker compose pull

# Build images that are different from the online source
docker compose build


# Save images to tar for backup in case docker goes down
echo "Saving images to fredt.tar"
docker save -o fredt.tar \
  postgis/postgis:16-3.4 \
  lparkinson/backend-flood-resilience-dt:1.2 \
  lparkinson/celery-flood-resilience-dt:1.2 \
  lparkinson/www-flood-resilience-dt:1.2 \
  lparkinson/geoserver-flood-resilience-dt:1.2 \
  redis:7 \


echo "Saving docker build dependency images to build_dep.tar"
docker save -o build_dep.tar \
  lparkinson/bg_flood:v0.9 \
  continuumio/miniconda3:23.10.0-1 \
  node:lts \
  docker.osgeo.org/geoserver:2.21.2 \
  nginx:stable
