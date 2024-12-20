# -*- coding: utf-8 -*-
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

"""
This script automates the retrieval and storage of geospatial data from various providers using the 'geoapis' library.
It populates the 'geospatial_layers' table in the database and stores user log information for tracking and reference.
"""

import geopandas as gpd

from src.digitaltwin import setup_environment, instructions_records_to_db, data_to_db
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Connects to various data providers to fetch geospatial data for the selected polygon, i.e., the catchment area.
    Subsequently, it populates the 'geospatial_layers' table in the database and stores user log information for
    tracking and reference.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)

    Returns
    -------
    None
        This function does not return any value.
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # Store 'static_boundary_instructions' records in the 'geospatial_layers' table in the database.
    instructions_records_to_db.store_instructions_records_to_db(engine)
    # Store geospatial layers data in the database
    data_to_db.store_geospatial_layers_data_to_db(engine, catchment_area)
    # Store user log information in the database
    data_to_db.user_log_info_to_db(engine, catchment_area)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.DEBUG
    )
