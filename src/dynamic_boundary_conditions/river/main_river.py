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
Main river script used to read and store REC data in the database, fetch OSM waterways data, create a river network
and its associated data, and generate the requested river model input for BG-Flood etc.
"""

import logging
import pathlib
from typing import Union, Optional, Tuple

import geopandas as gpd
import pyproj
import xarray as xr
from newzealidar.utils import get_dem_band_and_resolution_by_geometry
from shapely.geometry import LineString
from shapely.geometry import box
from sqlalchemy.engine import Engine

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.dynamic_boundary_conditions.river import (
    river_data_to_from_db,
    river_network_for_aoi,
    align_rec_osm,
    river_inflows,
    hydrograph,
    river_model_input
)
from src.dynamic_boundary_conditions.river.river_enum import BoundType

log = logging.getLogger(__name__)


def retrieve_hydro_dem_info(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> Tuple[xr.Dataset, LineString, Union[int, float]]:
    """
    Retrieves the Hydrologically Conditioned DEM (Hydro DEM) data, along with its spatial extent and resolution,
    for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    Tuple[xr.Dataset, LineString, Union[int, float]]
        A tuple containing the Hydro DEM data as a xarray Dataset, the spatial extent of the Hydro DEM as a LineString,
        and the resolution of the Hydro DEM as either an integer or a float.
    """
    # Retrieve the Hydro DEM data and resolution for the specified catchment area
    hydro_dem, res_no = get_dem_band_and_resolution_by_geometry(engine, catchment_area)
    # Extract the Coordinate Reference System (CRS) information from the 'hydro_dem' dataset
    hydro_dem_crs = pyproj.CRS(hydro_dem.spatial_ref.crs_wkt)
    # Get the bounding box (spatial extent) of the Hydro DEM and convert it to a GeoDataFrame
    hydro_dem_area = gpd.GeoDataFrame(geometry=[box(*hydro_dem.rio.bounds())], crs=hydro_dem_crs)
    # Get the exterior LineString from the GeoDataFrame
    hydro_dem_extent = hydro_dem_area.exterior.iloc[0]
    return hydro_dem, hydro_dem_extent, res_no


def get_hydro_dem_boundary_lines(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the boundary lines of the Hydrologically Conditioned DEM.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary lines of the Hydrologically Conditioned DEM.
    """
    # Obtain the spatial extent of the hydro DEM
    _, hydro_dem_extent, _ = retrieve_hydro_dem_info(engine, catchment_area)
    # Create a list of LineString segments from the exterior boundary coordinates
    dem_boundary_lines_list = [
        LineString([hydro_dem_extent.coords[i], hydro_dem_extent.coords[i + 1]])
        for i in range(len(hydro_dem_extent.coords) - 1)
    ]
    # Generate numbers from 1 up to the total number of boundary lines
    dem_boundary_line_numbers = range(1, len(dem_boundary_lines_list) + 1)
    # Create a GeoDataFrame containing the boundary line numbers and LineString geometries
    dem_boundary_lines = gpd.GeoDataFrame(
        data={'dem_boundary_line_no': dem_boundary_line_numbers},
        geometry=dem_boundary_lines_list,
        crs=catchment_area.crs
    )
    # Rename the geometry column to 'dem_boundary_line'
    dem_boundary_lines = dem_boundary_lines.rename_geometry('dem_boundary_line')
    return dem_boundary_lines


def remove_existing_river_inputs(bg_flood_dir: pathlib.Path) -> None:
    """
    Remove existing river input files from the specified directory.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory containing the river input files.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through all river input files in the directory
    for river_input_file in bg_flood_dir.glob('river[0-9]*.txt'):
        # Remove the file
        river_input_file.unlink()


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        flow_length_mins: int,
        time_to_peak_mins: Union[int, float],
        maf: bool = True,
        ari: Optional[int] = None,
        bound: BoundType = BoundType.MIDDLE,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Read and store REC data in the database, fetch OSM waterways data, create a river network and its associated data,
    and generate the requested river model input for BG-Flood.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    flow_length_mins : int
        Duration of the river flow in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when flow is at its greatest (reaches maximum).
    maf : bool = True
        Set to True to obtain MAF-based scenario data or False to obtain ARI-based scenario data.
    ari : Optional[int] = None
        The Average Recurrence Interval (ARI) value. Valid options are 5, 10, 20, 50, 100, or 1000.
        Mandatory when 'maf' is set to False, and should be set to None when 'maf' is set to True.
    bound : BoundType = BoundType.MIDDLE
        Set the type of bound (estimate) for the REC river inflow scenario data.
        Valid options include: 'BoundType.LOWER', 'BoundType.MIDDLE', or 'BoundType.UPPER'.
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
    # BG-Flood Model Directory
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    # Remove any existing river model inputs in the BG-Flood directory
    remove_existing_river_inputs(bg_flood_dir)

    # Store REC data to the database
    river_data_to_from_db.store_rec_data_to_db(engine)
    # Get the REC river network for the catchment area
    _, rec_network_data = river_network_for_aoi.get_rec_river_network(engine, catchment_area)

    try:
        # Obtain REC river inflow data along with the corresponding river input points used in the BG-Flood model
        rec_inflows_data = river_inflows.get_rec_inflows_with_input_points(
            engine, catchment_area, rec_network_data, distance_m=300)

        # Generate hydrograph data for the requested REC river scenario
        hydrograph_data = hydrograph.get_hydrograph_data(
            rec_inflows_data,
            flow_length_mins=flow_length_mins,
            time_to_peak_mins=time_to_peak_mins,
            maf=maf,
            ari=ari,
            bound=bound
        )

        # Generate river model inputs for BG-Flood
        river_model_input.generate_river_model_input(bg_flood_dir, hydrograph_data)

    except align_rec_osm.NoRiverDataException as error:
        # Log an info message to indicate the absence of river data
        log.info(error)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        flow_length_mins=2880,
        time_to_peak_mins=1440,
        maf=True,
        ari=None,
        bound=BoundType.MIDDLE,
        log_level=LogLevel.DEBUG
    )
