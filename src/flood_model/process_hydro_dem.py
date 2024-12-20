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

"""This script fetches LiDAR terrain data for a region of interest and creates a hydrologically-conditioned DEM."""

import json
import logging

import geopandas as gpd
import newzealidar.datasets
import newzealidar.process

from src.digitaltwin import setup_environment, tables
from src.digitaltwin.utils import LogLevel, setup_logging

log = logging.getLogger(__name__)


def ensure_lidar_datasets_initialised() -> None:
    """
    Check if LiDAR datasets table is initialised.
    This table holds URLs to data sources for LiDAR.
    If it is not initialised, then it initialises it by web-scraping OpenTopography which takes a long time.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Connect to database
    engine = setup_environment.get_connection_from_profile()
    # Check if datasets table initialised
    if not tables.check_table_exists(engine, "dataset"):
        # If it is not initialised, then initialise it
        log.info("dataset table does not exist, initialising LiDAR dataset information.")
        newzealidar.datasets.main()
    # Check that datasets_mapping is in the instructions.json file
    instructions_file_name = "instructions.json"
    with open(instructions_file_name, "r") as instructions_file:
        # Load content from the file
        instructions = json.load(instructions_file)["instructions"]
    dataset_mapping = instructions.get("dataset_mapping")
    # If the dataset_mapping does not exist on the instruction file then read it from the database
    if dataset_mapping is None:
        # Add dataset_mapping to instructions file, reading from database
        log.debug("instructions.json missing LiDAR dataset_mapping, filling from database.")
        newzealidar.utils.map_dataset_name(engine, instructions_file_name)


def process_dem(selected_polygon_gdf: gpd.GeoDataFrame) -> None:
    """
    Ensures hydrologically-conditioned DEM is processed for the given area and added to the database.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        The polygon defining the selected area to process the DEM for.

    Returns
    -------
    None
        This function does not return any value.
    """
    log.info("Processing LiDAR data into hydrologically conditioned DEM for area of interest.")
    newzealidar.process.main(selected_polygon_gdf)


def refresh_lidar_datasets() -> None:
    """
    Web-scrapes OpenTopography metadata to create the datasets table containing links to LiDAR data sources.
    Takes a long time to run but needs to be run periodically so that the datasets are up to date.

    Returns
    -------
    None
        This function does not return any value.
    """
    newzealidar.datasets.main()


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Retrieves LiDAR data for the selected polygon and processes it into a hydrologically-conditioned DEM.

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
    ensure_lidar_datasets_initialised()
    process_dem(selected_polygon_gdf)
