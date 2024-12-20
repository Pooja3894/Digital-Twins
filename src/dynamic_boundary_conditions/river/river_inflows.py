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
This script handles the task of obtaining REC river inflow data along with the corresponding river input points used
for the BG-Flood model.
"""

import logging

import geopandas as gpd
import pandas as pd
import numpy as np
import xarray as xr
from sqlalchemy.engine import Engine
import pyproj
from newzealidar.utils import get_dem_band_and_resolution_by_geometry

from src.dynamic_boundary_conditions.river import main_river, align_rec_osm

log = logging.getLogger(__name__)


def get_elevations_near_rec_entry_point(
        rec_inflows_row: pd.Series,
        hydro_dem: xr.Dataset) -> gpd.GeoDataFrame:
    """
    Extracts elevation values and their corresponding coordinates from the Hydrologically Conditioned DEM in the
    vicinity of the entry point of the REC river inflow segment.

    Parameters
    ----------
    rec_inflows_row : pd.Series
        Represents data pertaining to an individual REC river inflow segment, including its entry point into the
        catchment area and the boundary line it aligns with.
    hydro_dem : xr.Dataset
        Hydrologically Conditioned DEM for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing elevation values and their corresponding coordinates extracted from the
        Hydrologically Conditioned DEM in the vicinity of the entry point of the REC river inflow segment.
    """
    # Clip the Hydro DEM using the buffered DEM boundary line
    clipped_hydro_dem = hydro_dem.rio.clip([rec_inflows_row['dem_boundary_line_buffered']])
    # Get the x and y coordinates of the aligned REC entry point
    aligned_rec_entry_point = rec_inflows_row["aligned_rec_entry_point"]
    entry_point_x, entry_point_y = aligned_rec_entry_point.x, aligned_rec_entry_point.y
    # Find the indices of the REC entry point x and y coordinates in the clipped Hydro DEM
    entry_point_x_index = int(np.argmin(abs(clipped_hydro_dem['x'].values - entry_point_x)))
    entry_point_y_index = int(np.argmin(abs(clipped_hydro_dem['y'].values - entry_point_y)))
    # Define the starting and ending indices for the x coordinates in the clipped Hydro DEM
    x_start_index = max(0, entry_point_x_index - 2)
    x_end_index = min(entry_point_x_index + 3, len(clipped_hydro_dem['x']))
    # Define the starting and ending indices for the y coordinates in the clipped Hydro DEM
    y_start_index = max(0, entry_point_y_index - 2)
    y_end_index = min(entry_point_y_index + 3, len(clipped_hydro_dem['y']))
    # Extract the x and y coordinates within the defined range from the clipped Hydro DEM
    x_coord_range = clipped_hydro_dem['x'].values[slice(x_start_index, x_end_index)]
    y_coord_range = clipped_hydro_dem['y'].values[slice(y_start_index, y_end_index)]
    # Extract elevation values for the specified x and y coordinate ranges from the clipped Hydro DEM
    nearby_elevations = clipped_hydro_dem.sel(x=x_coord_range, y=y_coord_range).to_dataframe().reset_index()
    # Create Point objects for each row using 'x' and 'y' coordinates
    nearby_elevations['river_input_point'] = gpd.points_from_xy(nearby_elevations['x'], nearby_elevations['y'])
    # Remove unnecessary columns from the elevation data
    nearby_elevations.drop(columns=['x', 'y', 'band', 'spatial_ref', 'data_source', 'lidar_source'], inplace=True)
    # Rename the 'z' column to 'dem_elevation' for clarity and consistency
    nearby_elevations.rename(columns={'z': 'dem_elevation'}, inplace=True)
    # Extract the Coordinate Reference System (CRS) information from the 'hydro_dem' dataset
    hydro_dem_crs = pyproj.CRS(hydro_dem.spatial_ref.crs_wkt)
    # Convert to a GeoDataFrame with specified CRS and geometry column
    nearby_elevations = gpd.GeoDataFrame(nearby_elevations, geometry='river_input_point', crs=hydro_dem_crs)
    return nearby_elevations


def get_min_elevation_river_input_point(rec_inflows_row: pd.Series, hydro_dem: xr.Dataset) -> gpd.GeoDataFrame:
    """
    Locate the river input point with the lowest elevation, used for BG-Flood model river input, from the
    Hydrologically Conditioned DEM for the specific REC river inflow segment.

    Parameters
    ----------
    rec_inflows_row : pd.Series
        Represents data pertaining to an individual REC river inflow segment, including its entry point into the
        catchment area and the boundary line it aligns with.
    hydro_dem : xr.Dataset
        Hydrologically Conditioned DEM for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the river input point with the lowest elevation, used for BG-Flood model river input,
        from the Hydrologically Conditioned DEM for the specific REC river inflow segment.
    """
    # Extracts elevation values and their corresponding coordinates near the REC inflow entry point from the Hydro DEM
    nearby_elevations = get_elevations_near_rec_entry_point(rec_inflows_row, hydro_dem)
    # Determine the midpoint by calculating the centroid of all 'river_input_point' coordinates
    midpoint_coord = nearby_elevations['river_input_point'].unary_union.centroid
    # Calculate the distance between each 'river_input_point' and the midpoint
    nearby_elevations['distance'] = nearby_elevations['river_input_point'].distance(midpoint_coord)
    # Find the minimum elevation value
    min_elevation_value = nearby_elevations['dem_elevation'].min()
    # Extract the rows with the minimum elevation value
    min_elevations = nearby_elevations[nearby_elevations['dem_elevation'] == min_elevation_value]
    # Select the closest point to the midpoint based on the minimum distance
    min_elevation_entry_point = min_elevations.sort_values('distance').head(1)
    # Remove the unnecessary 'distance' column and reset the index
    min_elevation_entry_point = min_elevation_entry_point.drop(columns=['distance']).reset_index(drop=True)
    return min_elevation_entry_point


def get_rec_inflows_with_input_points(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec_network_data: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Obtain data for REC river inflow segments whose boundary points align with the boundary points of
    OpenStreetMap (OSM) waterways within a specified distance threshold, along with their corresponding
    river input points used for the BG-Flood model.

    Parameters
    -----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC river network data.
    distance_m : int = 300
        Distance threshold in meters for spatial proximity matching. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing data for REC river inflow segments whose boundary points align with the
        boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold,
        along with their corresponding river input points used for the BG-Flood model.

    Raises
    ------
    NoRiverDataException
        If no REC river segment is found crossing the catchment boundary.
    """
    # Obtain data for REC river inflow segments whose boundary points align with the boundary points of OSM waterways
    # within a specified distance threshold
    aligned_rec_inflows = align_rec_osm.get_rec_inflows_aligned_to_osm(
        engine, catchment_area, rec_network_data, distance_m)

    log.info("Determining the river input points used for the BG-Flood model.")
    # Get the boundary lines of the Hydrologically Conditioned DEM
    dem_boundary_lines = main_river.get_hydro_dem_boundary_lines(engine, catchment_area)
    # Perform a spatial join between the REC inflow data and the Hydro DEM boundary lines
    rec_inflows = gpd.sjoin(aligned_rec_inflows, dem_boundary_lines, how="left", predicate="intersects")
    # Merge with the Hydro DEM boundary lines data and remove unnecessary columns
    rec_inflows = rec_inflows.merge(dem_boundary_lines, on="dem_boundary_line_no", how="left")
    rec_inflows = rec_inflows.drop(columns=["index_right"])
    # Retrieve the Hydro DEM data and resolution for the specified catchment area
    hydro_dem, res_no = get_dem_band_and_resolution_by_geometry(engine, catchment_area)
    # Buffer the Hydro DEM boundary lines using the Hydro DEM resolution
    rec_inflows["dem_boundary_line_buffered"] = rec_inflows["dem_boundary_line"].buffer(distance=res_no, cap_style=2)
    # Add the Hydro DEM resolution information
    rec_inflows["dem_resolution"] = res_no
    # Create an empty GeoDataFrame to store REC inflows input
    rec_inflows_w_input_points = gpd.GeoDataFrame()
    # Iterate through each row in the 'rec_inflows' GeoDataFrame
    for _, row in rec_inflows.iterrows():
        # Locate the river input point used for BG-Flood model river input from the Hydro DEM
        river_input_point = get_min_elevation_river_input_point(row, hydro_dem)
        # Assign the lowest DEM elevation value to the 'dem_elevation' column in the current 'row'
        row['dem_elevation'] = river_input_point['dem_elevation'][0]
        # Assign the river input point geometry to the 'river_input_point' column in the current 'row'
        row['river_input_point'] = river_input_point['river_input_point'][0]
        # Append the updated 'row' to the 'rec_inflows_w_input_points' GeoDataFrame
        rec_inflows_w_input_points = rec_inflows_w_input_points.append(row, ignore_index=True)
    # Set 'river_input_point' as the geometry column and maintain the same CRS
    rec_inflows_w_input_points = gpd.GeoDataFrame(
        rec_inflows_w_input_points, geometry="river_input_point", crs=rec_inflows.crs)
    # Reset the index to ensure a clean sequential order
    rec_inflows_w_input_points = rec_inflows_w_input_points.reset_index(drop=True)
    return rec_inflows_w_input_points
