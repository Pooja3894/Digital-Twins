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
Get the locations used to fetch tide data from NIWA using the tide API.
"""

import logging

import geopandas as gpd
from shapely.geometry import LineString, Point
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

log = logging.getLogger(__name__)


class NoTideDataException(Exception):
    """Exception raised when no tide data is to be used for the BG-Flood model."""
    pass


def get_regional_council_clipped_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve regional council clipped data from the database based on the catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the regional council clipped data for the catchment area.
    """
    # Extract the catchment polygon from the GeoDataFrame
    catchment_polygon = catchment_area["geometry"][0]
    # Construct the query to retrieve the regional council clipped data
    command_text = """
    SELECT *
    FROM region_geometry_clipped AS rgc
    WHERE ST_Intersects(rgc.geometry, ST_GeomFromText(:catchment_polygon, 2193));
    """
    query = text(command_text).bindparams(
        catchment_polygon=str(catchment_polygon)
    )
    # Execute the query and retrieve the result as a GeoDataFrame
    regions_clipped = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return regions_clipped


def get_nz_coastline_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        distance_km: int = 1) -> gpd.GeoDataFrame:
    """
    Retrieve the New Zealand coastline data within a specified distance of the catchment area from the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    distance_km : int = 1
        Distance in kilometers used to buffer the catchment area for coastline retrieval. Default is 1 kilometer.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the New Zealand coastline data within the specified distance of the catchment area.
    """
    # Convert distance from kilometers to meters
    distance_m = distance_km * 1000
    # Buffer the catchment area to create a buffered polygon
    catchment_area_buffered = catchment_area.buffer(distance=distance_m, join_style=2)
    catchment_area_buffered_polygon = catchment_area_buffered.iloc[0]
    # Construct the query to retrieve the New Zealand coastline data within the buffered catchment area
    command_text = """
    SELECT *
    FROM nz_coastlines AS coast
    WHERE ST_Intersects(coast.geometry, ST_GeomFromText(:catchment_area_buffered_polygon, 2193));
    """
    query = text(command_text).bindparams(
        catchment_area_buffered_polygon=str(catchment_area_buffered_polygon)
    )
    # Execute the query and retrieve the result as a GeoDataFrame
    coastline = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return coastline


def get_catchment_boundary_info(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get information about the boundary segments of the catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing information about the boundary segments of the catchment area.

    Raises
    ------
    ValueError
        If the position of a catchment boundary line cannot be identified.
    """
    # Retrieve the coordinates of the exterior boundary of the catchment area
    boundary_coords = catchment_area["geometry"].iloc[0].exterior.coords
    # Create an empty list to store boundary segment properties
    boundary_segments = []
    # Loop through each boundary line segment
    for i in range(len(boundary_coords) - 1):
        # Get the start and end points of the current boundary segment
        start_point, end_point = boundary_coords[i], boundary_coords[i + 1]
        # Find the centroid of the current boundary segment
        centroid = Point((start_point[0] + end_point[0]) / 2, (start_point[1] + end_point[1]) / 2)
        # Determine the position of the centroid relative to the catchment area
        if centroid.x == min(boundary_coords)[0]:
            position = 'left'
        elif centroid.x == max(boundary_coords)[0]:
            position = 'right'
        elif centroid.y == min(boundary_coords)[1]:
            position = 'bot'
        elif centroid.y == max(boundary_coords)[1]:
            position = 'top'
        else:
            raise ValueError("Failed to identify catchment boundary line position.")
        # Create a LineString object for the current boundary segment
        boundary_geom = LineString([start_point, end_point])
        # Add the boundary segment and its properties to the list
        boundary_segments.append({'line_position': position, 'boundary': boundary_geom})
    # Convert the list of boundary segments to a GeoDataFrame
    boundary_info = gpd.GeoDataFrame(boundary_segments, geometry='boundary', crs=catchment_area.crs)
    # Calculate and add the centroid of each boundary segment as a new column
    boundary_info['centroid'] = boundary_info['boundary'].centroid
    return boundary_info


def get_catchment_boundary_lines(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the boundary lines of the catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary lines of the catchment area.
    """
    # Get the boundary information of the catchment area
    boundary_info = get_catchment_boundary_info(catchment_area)
    # Select the required columns and rename 'boundary' to 'geometry'
    boundary_lines = boundary_info[['line_position', 'boundary']].rename(columns={'boundary': 'geometry'})
    # Set the 'geometry' column as the active geometry column
    boundary_lines = boundary_lines.set_geometry('geometry', crs=catchment_area.crs)
    return boundary_lines


def get_catchment_boundary_centroids(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the centroids of the boundary lines of the catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the centroids of the boundary lines of the catchment area.
    """
    # Get the boundary information of the catchment area
    boundary_info = get_catchment_boundary_info(catchment_area)
    # Select the required columns and rename 'centroid' to 'geometry'
    boundary_centroids = boundary_info[['line_position', 'centroid']].rename(columns={'centroid': 'geometry'})
    # Set the 'geometry' column as the active geometry column
    boundary_centroids = boundary_centroids.set_geometry('geometry', crs=catchment_area.crs)
    return boundary_centroids


def get_non_intersection_centroid_position(
        catchment_area: gpd.GeoDataFrame,
        non_intersection_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Determine the positions of non-intersection centroid points relative to the boundary lines of the catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    non_intersection_area : gpd.GeoDataFrame
        A GeoDataFrame representing the non-intersection area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the positions of non-intersection centroid points relative to the catchment boundary
        lines. The GeoDataFrame includes the 'position' column denoting the relative position and the 'geometry' column
        representing the centroid points of the non-intersection areas.
    """
    # Explode the non-intersection area to ensure each geometry is a single part
    non_intersections = non_intersection_area.explode(index_parts=False, ignore_index=True)
    # Calculate the centroid for each non-intersection geometry
    non_intersections['centroid'] = non_intersections.centroid
    # Get the boundary lines of the catchment area
    boundary_lines = get_catchment_boundary_lines(catchment_area)
    # Identify the closest boundary line for each non-intersection centroid point
    non_intersections['position'] = non_intersections['centroid'].apply(
        lambda centroid: boundary_lines.loc[boundary_lines['geometry'].distance(centroid).idxmin(), 'line_position']
    )
    # Select the required columns and rename 'centroid' to 'geometry'
    non_intersections = non_intersections[['position', 'centroid']].rename(columns={'centroid': 'geometry'})
    # Set the 'geometry' column as the active geometry column
    non_intersections = non_intersections.set_geometry('geometry')
    return non_intersections


def get_tide_query_locations(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        distance_km: int = 1) -> gpd.GeoDataFrame:
    """
    Get the locations used to fetch tide data from NIWA using the tide API.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    distance_km : int = 1
        Distance in kilometers used to buffer the catchment area for coastline retrieval. Default is 1 kilometer.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the locations used to fetch tide data from NIWA using the tide API.

    Raises
    ------
    NoTideDataException
        If no coastline is found within the specified distance of the catchment area.
    """
    log.info("Identifying query locations used for fetching 'tide' data from NIWA.")
    # Get the regional council clipped data for the catchment area
    regions_clipped = get_regional_council_clipped_from_db(engine, catchment_area)
    # Determine the non-intersection area
    non_intersection_area = catchment_area.overlay(regions_clipped, how='difference')
    # Check if there is no non-intersection area
    if non_intersection_area.empty:
        # Get the New Zealand coastline data within the specified distance of the catchment area
        coastline = get_nz_coastline_from_db(engine, catchment_area, distance_km)
        # Check if coastline data is empty
        if coastline.empty:
            # If no coastline is found, raise an exception
            raise NoTideDataException(
                f"No query locations were found within {distance_km}km of the catchment area; "
                f"hence, 'tide' data will not be utilised in the BG-Flood model.")
        else:
            # Extract the geometry of the coastline
            coastline_geom = coastline['geometry'].iloc[0]
            # Get the centroid positions of the catchment boundary lines
            boundary_centroids = get_catchment_boundary_centroids(catchment_area)
            # Calculate the distance from each boundary centroid to the coastline
            boundary_centroids['dist_to_coast'] = boundary_centroids.distance(coastline_geom)
            # Select the boundary centroid closest to the coastline
            tide_query_location = boundary_centroids.sort_values('dist_to_coast').head(1)
            # Rename the 'line_position' column to 'position' for consistency
            tide_query_location = tide_query_location[['line_position', 'geometry']].rename(
                columns={'line_position': 'position'})
    else:
        # Determine the positions of non-intersection centroid points relative to the catchment boundary lines
        non_intersections = get_non_intersection_centroid_position(catchment_area, non_intersection_area)
        # Group by the 'position' column and calculate the centroid for each group
        grouped = non_intersections.groupby('position')['geometry'].apply(lambda x: x.unary_union.centroid)
        tide_query_location = grouped.reset_index().set_crs(non_intersections.crs)
    # Convert the CRS of the tide query locations to ensure compatibility with the tide API
    tide_query_location = tide_query_location.to_crs(4326).reset_index(drop=True)
    return tide_query_location
