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

FROM node:lts AS build-stage

WORKDIR /app
# Install node_modules
COPY visualisation/package*.json ./
RUN npm ci --ignore-scripts

# Copy License file into image root
COPY ./LICENSE ../LICENSE
# Copy visualisation source files into image
COPY ["visualisation/*.js", "visualisation/*.json", "visualisation/.env.production", "./"]
COPY visualisation/src/ src/
COPY visualisation/public/ public/

# Build code for production style server
RUN npm run build

FROM nginx:stable AS production-stage

# Serve built files using nginx
RUN mkdir /app
COPY --from=build-stage /app/dist /app
COPY visualisation/nginx.conf /etc/nginx/nginx.conf

COPY visualisation/entrypoint.sh /entrypoint.sh
RUN chmod +x entrypoint.sh

# Expose nginx web-server on http port (80)
EXPOSE 80

# Run entrypoint script for initialising environment variables before starting server
ENTRYPOINT ["/entrypoint.sh"]
