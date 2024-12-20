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
This script handles the task of obtaining data for REC river inflow segments whose boundary points align with the
boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold.
"""

import logging
from typing import Dict, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from sqlalchemy.engine import Engine

from src.dynamic_boundary_conditions.river import main_river, osm_waterways

log = logging.getLogger(__name__)


class NoRiverDataException(Exception):
    """Exception raised when no river data is to be used for the BG-Flood model."""
    pass


def get_rec_network_data_on_bbox(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Obtain REC river network data that intersects with the catchment area boundary, along with the corresponding
    intersection points on the boundary.

    Parameters
    -----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC river network data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing REC river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Raises
    ------
    NoRiverDataException
        If no REC river segment is found crossing the catchment boundary.
    """
    # Obtain the spatial extent of the hydro DEM
    _, hydro_dem_extent, _ = main_river.retrieve_hydro_dem_info(engine, catchment_area)
    # Select features that intersect with the hydro DEM extent
    rec_on_bbox = rec_network_data[rec_network_data.intersects(hydro_dem_extent)].reset_index(drop=True)
    # Check if there are REC river segments that cross the hydro DEM extent
    if rec_on_bbox.empty:
        # If no REC river segment is found, raise an exception
        raise NoRiverDataException(
            "No relevant river data could be found for the catchment area. "
            "As a result, river data will not be used in the BG-Flood model.")
    # Determine the points of intersection along the boundary
    rec_on_bbox["rec_boundary_point"] = rec_on_bbox["geometry"].intersection(hydro_dem_extent)
    # Rename the 'geometry' column to 'rec_river_line' and set the geometry to 'rec_boundary_point'
    rec_on_bbox = rec_on_bbox.rename_geometry("rec_river_line").set_geometry("rec_boundary_point")
    return rec_on_bbox


def get_single_intersect_inflows(rec_on_bbox: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies REC river segments that intersect the catchment boundary once, then retrieves the segments
    that are inflows into the catchment area, along with their corresponding inflow boundary points.

    Parameters
    ----------
    rec_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC river segments that intersect the catchment boundary once and
        are inflows into the catchment area, along with their corresponding inflow boundary points.
    """
    # Check if there are any single Point geometries
    if any(rec_on_bbox.geom_type == "Point"):
        # Select only the records where 'rec_boundary_point' is a single point
        single_intersect = rec_on_bbox[rec_on_bbox["rec_boundary_point"].geom_type == "Point"]
        # Identify the inflow boundary points
        single_intersect_inflow = single_intersect[
            ((single_intersect["node_direction"] == "to") & (single_intersect["node_intersect_aoi"] == "last_node")) |
            ((single_intersect["node_direction"] == "from") & (single_intersect["node_intersect_aoi"] == "first_node"))
            ]
        # Create a new column for inflow points for consistency purposes
        single_intersect_inflow["rec_inflow_point"] = single_intersect_inflow["rec_boundary_point"]
        # Set the geometry of the GeoDataFrame to 'rec_inflow_point'
        single_intersect_inflow.set_geometry("rec_inflow_point", inplace=True)
        # Reset the index
        single_intersect_inflow.reset_index(drop=True, inplace=True)
    else:
        # No single Point geometries found, return an empty GeoDataFrame
        single_intersect_inflow = gpd.GeoDataFrame()
    return single_intersect_inflow


def get_exploded_multi_intersect(rec_on_bbox: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies REC river segments that intersect the catchment boundary multiple times,
    transforms MultiPoint geometries into individual Point geometries (boundary points),
    calculates the distance along the river segment for each boundary point, and
    adds a new column containing boundary points sorted by their distance along the river.

    Parameters
    ----------
    rec_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC river segments that intersect the catchment boundary multiple times,
        along with the corresponding intersection points on the boundary, sorted by distance along the river.
    """
    # Select only the records where 'rec_boundary_point' is a collection of multiple points (MultiPoint)
    multi_intersect = rec_on_bbox[rec_on_bbox["rec_boundary_point"].geom_type == "MultiPoint"]
    # Explode multi-part geometries into multiple single geometries
    multi_intersect_explode = multi_intersect.explode()
    # Calculate the distance along the river for each Point and add it as a new column
    multi_intersect_explode["distance_along_river"] = multi_intersect_explode.apply(
        lambda row: row["rec_river_line"].project(row["rec_boundary_point"]), axis=1)
    # Sort the exploded points by 'objectid' and 'distance_along_river'
    multi_intersect_explode.sort_values(by=["objectid", "distance_along_river"], inplace=True)
    # Group the exploded Points by 'objectid' and collect them as a list (already sorted by distance along the river)
    exploded_intersect_by_distance = (
        multi_intersect_explode
        .groupby("objectid")["rec_boundary_point"]
        .apply(list)
        .reset_index(name="rec_boundary_point_explode")
    )
    # Merge the list of exploded boundary points back
    multi_intersect = multi_intersect.merge(exploded_intersect_by_distance, on="objectid", how="left")
    return multi_intersect


def determine_multi_intersect_inflow_index(multi_intersect_row: pd.Series) -> int:
    """
    Determines the index that represents the position of the first inflow boundary point along a REC river segment.

    Parameters
    ----------
    multi_intersect_row : pd.Series
        A REC river segment that intersects the catchment boundary multiple times, along with the
        corresponding intersection points on the boundary, sorted by distance along the river.

    Returns
    -------
    int
        An integer that represents the position of the first inflow boundary point along a REC river segment.

    Raises
    ------
    ValueError
        If the index that represents the position of the first inflow boundary point along a REC river segment
        cannot be determined.
    """
    # Extract the 'node_direction' and 'node_intersect_aoi' attributes from the input Series
    node_direction = multi_intersect_row["node_direction"]
    node_intersect_aoi = multi_intersect_row["node_intersect_aoi"]
    # Define a dictionary to map conditions to inflow_index values
    condition_mapping = {
        ("to", "both_nodes"): 1,
        ("to", "first_node"): 1,
        ("from", None): 1,
        ("from", "last_node"): 1,
        ("from", "both_nodes"): 0,
        ("from", "first_node"): 0,
        ("to", None): 0,
        ("to", "last_node"): 0,
    }
    # Check if the condition exists in the dictionary, otherwise default to None
    inflow_index = condition_mapping.get((node_direction, node_intersect_aoi), None)
    # If none of the conditions are met, raise a ValueError with an informative message
    if inflow_index is None:
        objectid = multi_intersect_row["objectid"]
        raise ValueError(f"Unable to determine the inflow index for REC river segment {objectid}.")
    return inflow_index


def categorize_exploded_multi_intersect(multi_intersect: gpd.GeoDataFrame) -> Dict[int, Dict[str, List[Point]]]:
    """
    Categorizes boundary points of REC river segments that intersect the catchment boundary multiple times into
    'inflow' and 'outflow' based on their sequential positions along the river segment etc.

    Parameters
    ----------
    multi_intersect : gpd.GeoDataFrame
        A GeoDataFrame containing the REC river segments that intersect the catchment boundary multiple times,
        along with the corresponding intersection points on the boundary, sorted by distance along the river.

    Returns
    -------
    Dict[int, Dict[str, List[Point]]]
        A dictionary where the keys represent the 'objectid' values of REC river segments, and the values are
        dictionaries. Each of these dictionaries contains two lists: 'inflow' and 'outflow,' which respectively
        represent the boundary points where water flows into and out of the catchment area.
    """
    # Initialize an empty dictionary to store categorized boundary points for each REC river segment
    categorized_multi_intersect: Dict[int, Dict[str, List[Point]]] = {}

    # Iterate through each REC river segment
    for _, row in multi_intersect.iterrows():
        # Extract the 'objectid' and list of exploded boundary points
        objectid, boundary_points = row["objectid"], row["rec_boundary_point_explode"]
        # Determines the index that represents the position of the first inflow boundary point
        inflow_index = determine_multi_intersect_inflow_index(row)

        # Initialize a dictionary to categorize boundary points as 'inflow' or 'outflow'
        categorized_points = dict(outflow=[], inflow=[])
        # Iterate through the list of exploded boundary points and categorize each one
        for index, point in enumerate(boundary_points):
            # Determine the category based on their order along the river segment and inflow index
            category = "inflow" if index % 2 == inflow_index else "outflow"
            # Append the current 'point' to the appropriate category
            categorized_points[category].append(point)

        # Associate the categorized points with the 'objectid' and store them in the main dictionary
        categorized_multi_intersect[objectid] = categorized_points
    return categorized_multi_intersect


def get_multi_intersect_inflows(rec_on_bbox: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies REC river segments that intersect the catchment boundary multiple times, then retrieves the segments
    that are inflows into the catchment area, along with their corresponding inflow boundary points.

    Parameters
    ----------
    rec_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC river segments that intersect the catchment boundary multiple times and
        are inflows into the catchment area, along with their corresponding inflow boundary points.
    """
    # Check if there are any MultiPoint geometries
    if any(rec_on_bbox.geom_type == "MultiPoint"):
        # Identify and explode MultiPoint geometries into individual Point geometries
        multi_intersect = get_exploded_multi_intersect(rec_on_bbox)
        # Categorize the exploded Point geometries into 'inflow' and 'outflow' categories
        categorized_multi_intersect = categorize_exploded_multi_intersect(multi_intersect)
        # Extract the 'objectid' and the last inflow point for each REC river segment
        inflow_points = [(objectid, data["inflow"][-1]) for objectid, data in categorized_multi_intersect.items()]
        # Create a DataFrame from the extracted inflow points with columns 'objectid' and 'rec_inflow_point'
        inflow_points_df = pd.DataFrame(inflow_points, columns=["objectid", "rec_inflow_point"])
        # Merge the inflow points DataFrame with the original MultiPoint GeoDataFrame
        multi_point_inflows = multi_intersect.merge(inflow_points_df, on="objectid", how="left")
        # Convert the 'rec_inflow_point' column to a geometry data type
        multi_point_inflows["rec_inflow_point"] = multi_point_inflows["rec_inflow_point"].astype("geometry")
        # Set the geometry column and coordinate reference system (CRS) for the GeoDataFrame
        multi_point_inflows = multi_point_inflows.set_geometry("rec_inflow_point", crs=multi_point_inflows.crs)
        # Drop the temporary column used for exploding MultiPoint geometries
        multi_point_inflows = multi_point_inflows.drop(columns=["rec_boundary_point_explode"])
        # Reset the index
        multi_point_inflows.reset_index(drop=True, inplace=True)
    else:
        # No MultiPoint geometries found, return an empty GeoDataFrame
        multi_point_inflows = gpd.GeoDataFrame()
    return multi_point_inflows


def get_rec_inflows_on_bbox(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Obtain REC river segments that are inflows into the specified catchment area, along with their corresponding
    inflow boundary points.

    Parameters
    -----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC river network data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing REC river segments that are inflows into the catchment area, along with their
        corresponding inflow boundary points.

    Raises
    ------
    NoRiverDataException
        If no REC river segment is found crossing the catchment boundary.
    """
    log.info("Extracting REC river segments that are inflows into the requested catchment area.")
    # Get REC river network segments that intersect with the catchment area boundary
    rec_on_bbox = get_rec_network_data_on_bbox(engine, catchment_area, rec_network_data)
    # Get REC river segments that intersect the catchment boundary once and flow into the catchment area
    single_intersect_inflow = get_single_intersect_inflows(rec_on_bbox)
    # Get REC river segments that intersect the catchment boundary multiple times and flow into the catchment area
    multi_intersect_inflow = get_multi_intersect_inflows(rec_on_bbox)
    # Combine inflows from both single and multiple intersection segments into a single GeoDataFrame
    combined_inflows = pd.concat([single_intersect_inflow, multi_intersect_inflow], ignore_index=True)
    rec_inflows_on_bbox = gpd.GeoDataFrame(combined_inflows)
    return rec_inflows_on_bbox


def get_osm_waterways_on_bbox(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve OpenStreetMap (OSM) waterway data that intersects with the catchment boundary,
    along with the corresponding intersection points on the boundary.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing OpenStreetMap (OSM) waterway data that intersects with the catchment boundary,
        along with the corresponding intersection points on the boundary.
    """
    # Obtain the spatial extent of the hydro DEM
    _, hydro_dem_extent, _ = main_river.retrieve_hydro_dem_info(engine, catchment_area)
    # Fetch OSM waterway data for the catchment area
    osm_waterways_data = osm_waterways.get_osm_waterways_data(catchment_area)

    log.info("Extracting OpenStreetMap (OSM) waterways that intersect the boundary of the requested catchment area.")
    # Select features that intersect with the hydro DEM extent
    osm_waterways_on_bbox = osm_waterways_data[osm_waterways_data.intersects(hydro_dem_extent)].reset_index(drop=True)
    # Determine the points of intersection along the boundary
    osm_waterways_on_bbox["osm_boundary_point"] = osm_waterways_on_bbox["geometry"].intersection(hydro_dem_extent)
    # Rename the 'geometry' column to 'osm_river_line' and set the geometry to 'osm_boundary_point'
    osm_waterways_on_bbox = osm_waterways_on_bbox.rename_geometry("osm_river_line").set_geometry("osm_boundary_point")
    # Explode multi-point geometries into multiple single geometries
    osm_waterways_on_bbox = osm_waterways_on_bbox.explode(ignore_index=True)
    return osm_waterways_on_bbox


def align_rec_with_osm(
        rec_inflows_on_bbox: gpd.GeoDataFrame,
        osm_waterways_on_bbox: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Aligns the boundary points of REC river inflow segments with the boundary points of OpenStreetMap (OSM) waterways
    within a specified distance threshold.

    Parameters
    ----------
    rec_inflows_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC river network segments where water flows into the catchment area,
        along with their corresponding inflow boundary points.
    osm_waterways_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing OpenStreetMap (OSM) waterway data that intersects with the catchment boundary,
        along with the corresponding intersection points on the boundary.
    distance_m : int = 300
        Distance threshold in meters for spatial proximity matching. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary points of REC river inflow segments aligned with the boundary points of
        OpenStreetMap (OSM) waterways within a specified distance threshold.
    """
    log.info("Aligning the boundary points of REC river inflow segments with the boundary points of OSM waterways.")
    # Select relevant columns from REC data
    rec_columns = ["objectid", rec_inflows_on_bbox.geometry.name]
    rec_on_bbox = rec_inflows_on_bbox[rec_columns]
    # Select relevant columns from OSM data
    osm_columns = ["id", osm_waterways_on_bbox.geometry.name]
    osm_on_bbox = osm_waterways_on_bbox[osm_columns]
    # Perform a spatial join to find the nearest OSM waterway features within a specified distance
    joined_rec_osm = gpd.sjoin_nearest(
        rec_on_bbox, osm_on_bbox, how="inner", distance_col="distances", max_distance=distance_m)
    # Group the joined data based on the 'index_right' and 'id' attributes of OSM waterway features
    grouped = joined_rec_osm.groupby(['index_right', 'id'])
    # Create an empty GeoDataFrame to store the aligned data
    aligned_rec_osm = gpd.GeoDataFrame()
    # Iterate through each group in the grouped data
    for _, group_data in grouped:
        # Sort the group_data by distance
        group_data = group_data.sort_values(by="distances")
        # Remove duplicate OSM waterway features and keep the closest ones
        group_data = group_data.drop_duplicates(subset="id", keep="first")
        # Concatenate the processed group_data with the aligned_rec_osm GeoDataFrame
        aligned_rec_osm = pd.concat([aligned_rec_osm, group_data])
    # Select relevant columns and merge with OSM waterway data
    aligned_rec_osm = aligned_rec_osm[["objectid", "index_right"]]
    aligned_rec_osm = aligned_rec_osm.merge(osm_on_bbox, left_on="index_right", right_index=True, how="left")
    # Drop the 'index_right' column to clean up the DataFrame
    aligned_rec_osm = aligned_rec_osm.drop(columns=["index_right"]).reset_index(drop=True)
    # Create a GeoDataFrame using the 'osm_boundary_point' column as the geometry
    aligned_rec_osm = gpd.GeoDataFrame(aligned_rec_osm, geometry="osm_boundary_point")
    # Rename the geometry column to 'aligned_rec_entry_point' for clarity
    aligned_rec_osm = aligned_rec_osm.rename_geometry("aligned_rec_entry_point")
    return aligned_rec_osm


def get_rec_inflows_aligned_to_osm(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec_network_data: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Obtain data for REC river inflow segments whose boundary points align with the boundary points of
    OpenStreetMap (OSM) waterways within a specified distance threshold.

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
        boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold.

    Raises
    ------
    NoRiverDataException
        If no REC river segment is found crossing the catchment boundary.
    """
    # Obtain REC river network segments where water flows into the catchment area
    rec_inflows_on_bbox = get_rec_inflows_on_bbox(engine, catchment_area, rec_network_data)
    # Retrieve OpenStreetMap (OSM) waterway data that intersects with the catchment area boundary
    osm_waterways_on_bbox = get_osm_waterways_on_bbox(engine, catchment_area)
    # Align REC river inflow boundary points with OSM waterway boundary points within the specified distance
    aligned_rec_osm = align_rec_with_osm(rec_inflows_on_bbox, osm_waterways_on_bbox, distance_m)
    # Extract relevant columns
    aligned_rec_entry_points = aligned_rec_osm[["objectid", "aligned_rec_entry_point"]]
    # Combine aligned REC entry points with REC inflows data
    aligned_rec_inflows = aligned_rec_entry_points.merge(rec_inflows_on_bbox, on="objectid", how="left")
    # Move the 'aligned_rec_entry_point' column to the last position
    aligned_rec_inflows["aligned_rec_entry_point"] = aligned_rec_inflows.pop("aligned_rec_entry_point")
    # Drop unnecessary column
    aligned_rec_inflows.drop(columns=["rec_inflow_point"], inplace=True)
    return aligned_rec_inflows
