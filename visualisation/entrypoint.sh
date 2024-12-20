#!/bin/bash
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


# Used by docker to import environment variables into a docker container without baking them into the image

ROOT_DIR=/app
# Find the list of VUE_APP_ variables in the environment variables
VUE_ENV_VARS=$(printenv | grep -o "VUE_APP_\w*")

echo "Replacing env constants in JS"
echo "Env constants = ${VUE_ENV_VARS}"
for FILE in "$ROOT_DIR"/js/app.*.js* "$ROOT_DIR"/index.html
do
  echo "Processing $FILE ...";

  for VAR_NAME in $VUE_ENV_VARS;
  do
    # Use variable indirection to lookup the value of the variable
    VAR_VALUE=$(eval "echo \${$VAR_NAME}")
    # Replace all instances of the string $VAR_NAME with $VAR_VALUE, allowing it to fail if it can't find it
    sed -i 's|'"${VAR_NAME}"'|'"${VAR_VALUE}"'|g' $FILE || true
  done
done
echo "Finished processing files for env constants"

echo "Starting nginx server now."
# Run the nginx server
nginx -g 'daemon off;'
