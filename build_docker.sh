#!/usr/bin/env bash

# Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
