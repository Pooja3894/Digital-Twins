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
Main rainfall script used to fetch and store rainfall data in the database, and to generate the requested
rainfall model input for BG-Flood, etc.
"""

import pathlib
from typing import Optional, Union

import geopandas as gpd

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.dynamic_boundary_conditions.rainfall.rainfall_enum import RainInputType, HyetoMethod
from src.dynamic_boundary_conditions.rainfall import (
    rainfall_sites,
    thiessen_polygons,
    hirds_rainfall_data_to_db,
    hirds_rainfall_data_from_db,
    hyetograph,
    rainfall_model_input,
)


def remove_existing_rain_inputs(bg_flood_dir: pathlib.Path) -> None:
    """
    Remove existing rain input files from the specified directory.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        BG-Flood model directory containing the rain input files.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through all rain input files in the directory
    for rain_input_file in bg_flood_dir.glob('rain_forcing.*'):
        # Remove the file
        rain_input_file.unlink()


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        rcp: Optional[float],
        time_period: Optional[str],
        ari: float,
        storm_length_mins: int,
        time_to_peak_mins: Union[int, float],
        increment_mins: int,
        hyeto_method: HyetoMethod,
        input_type: RainInputType,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Fetch and store rainfall data in the database, and generate the requested rainfall model input for BG-Flood.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    rcp : Optional[float]
        Representative Concentration Pathway (RCP) value. Valid options are 2.6, 4.5, 6.0, 8.5, or None
        for historical data.
    time_period : Optional[str]
        Future time period. Valid options are "2031-2050", "2081-2100", or None for historical data.
    ari : float
        Average Recurrence Interval (ARI) value. Valid options are 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    storm_length_mins : int
        Storm duration in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    hyeto_method : HyetoMethod
        Hyetograph method to be used. Valid options are HyetoMethod.ALT_BLOCK or HyetoMethod.CHICAGO.
    input_type: RainInputType
        The type of rainfall model input to be generated. Valid options are 'uniform' or 'varying',
        representing spatially uniform rain input (text file) or spatially varying rain input (NetCDF file).
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
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=4326)

    # BG-Flood Model Directory
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    # Remove any existing rainfall model inputs in the BG-Flood directory
    remove_existing_rain_inputs(bg_flood_dir)

    # Fetch rainfall sites data from the HIRDS website and store it to the database
    rainfall_sites.rainfall_sites_to_db(engine)

    # Compute the coverage areas (Thiessen Polygons) for all rainfall sites across NZ and store them in the database
    thiessen_polygons.thiessen_polygons_to_db(engine)

    # Get rainfall sites coverage areas (Thiessen Polygons) that intersect or are within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_area)
    # Fetch and store rainfall depth data for all sites within the catchment area in the database
    hirds_rainfall_data_to_db.rainfall_data_to_db(engine, sites_in_catchment, idf=False)

    # Retrieve rainfall depth data from the database for all sites within the catchment area based on a
    # user-requested scenario
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, sites_in_catchment, rcp, time_period, ari, idf=False)

    # Get hyetograph data for all sites within the catchment area
    hyetograph_data = hyetograph.get_hyetograph_data(
        rain_depth_in_catchment=rain_depth_in_catchment,
        storm_length_mins=storm_length_mins,
        time_to_peak_mins=time_to_peak_mins,
        increment_mins=increment_mins,
        interp_method="cubic",
        hyeto_method=hyeto_method)

    # Calculate the size and percentage of the catchment area covered by each rainfall site
    sites_coverage = rainfall_model_input.sites_coverage_in_catchment(sites_in_catchment, catchment_area)
    # Generate the requested rainfall model input for BG-Flood
    rainfall_model_input.generate_rain_model_input(hyetograph_data, sites_coverage, bg_flood_dir, input_type=input_type)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        rcp=2.6,
        time_period="2031-2050",
        ari=100,
        storm_length_mins=2880,
        time_to_peak_mins=1440,
        increment_mins=10,
        hyeto_method=HyetoMethod.ALT_BLOCK,
        input_type=RainInputType.UNIFORM,
        log_level=LogLevel.DEBUG
    )
