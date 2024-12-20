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
Calculate the area covered by each rainfall site throughout New Zealand and store it in the database.
Retrieve the coverage areas (Thiessen polygons) for all rainfall sites located within the catchment area.
"""

import logging

import geopandas as gpd
import pandas as pd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.digitaltwin import tables
from src.digitaltwin.utils import get_nz_boundary

log = logging.getLogger(__name__)


def get_sites_within_aoi(engine: Engine, area_of_interest: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get all rainfall sites within the area of interest from the database and return the required data as a
    GeoDataFrame.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the rainfall sites within the area of interest.
    """
    # Extract the geometry of the area of interest
    aoi_polygon = area_of_interest["geometry"].iloc[0]
    # Construct the query to fetch rainfall sites within the area of interest
    command_text = """
    SELECT *
    FROM rainfall_sites AS rs
    WHERE ST_Within(rs.geometry, ST_GeomFromText(:aoi_polygon, 4326));
    """
    query = text(command_text).bindparams(aoi_polygon=str(aoi_polygon))
    # Execute the query and retrieve the results as a GeoDataFrame
    sites_in_aoi = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Reset the index
    sites_in_aoi.reset_index(drop=True, inplace=True)
    return sites_in_aoi


def thiessen_polygons_calculator(
        area_of_interest: gpd.GeoDataFrame,
        sites_in_aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Create Thiessen polygons for rainfall sites within the area of interest and calculate the area covered by each
    rainfall site.

    Parameters
    ----------
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.
    sites_in_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the Thiessen polygons, site information, and area covered by each rainfall site.

    Raises
    ------
    ValueError
        - If the provided 'area_of_interest' GeoDataFrame does not contain any data.
        - If the provided 'sites_in_aoi' GeoDataFrame does not contain any data.
    """
    # Check if the area of interest GeoDataFrame is empty
    if area_of_interest.empty:
        raise ValueError("No data available for 'area_of_interest' passed as argument.")
    # Check if the rainfall sites GeoDataFrame is empty
    if sites_in_aoi.empty:
        raise ValueError("No data available for 'sites_in_aoi' passed as argument.")
    # Convert the rainfall site coordinates to an array of coordinates
    coordinates = points_to_coords(sites_in_aoi["geometry"])
    # Extract the geometry of the area of interest
    aoi_polygon = area_of_interest["geometry"].iloc[0]
    # Generate Voronoi regions from the coordinates within the area of interest
    region_polys, region_pts = voronoi_regions_from_coords(coordinates, aoi_polygon, per_geom=False)
    voronoi_regions = list(region_polys.values())
    sites_in_voronoi_order = pd.DataFrame()
    for site_index in region_pts.values():
        site_index = site_index[0]
        site = sites_in_aoi.filter(items=[site_index], axis=0)
        sites_in_voronoi_order = pd.concat([sites_in_voronoi_order, site])
    # Create a GeoDataFrame with Thiessen polygons, site information, and area covered by each rainfall site
    rainfall_sites_voronoi = gpd.GeoDataFrame(sites_in_voronoi_order, geometry=voronoi_regions, crs=4326)
    rainfall_sites_voronoi["area_in_km2"] = rainfall_sites_voronoi.to_crs(3857).area / 1e6
    rainfall_sites_voronoi = rainfall_sites_voronoi[["site_id", "site_name", "area_in_km2", "geometry"]]
    return rainfall_sites_voronoi


def thiessen_polygons_to_db(engine: Engine) -> None:
    """
    Store the data representing the Thiessen polygons, site information, and the area covered by
    each rainfall site in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    table_name = "rainfall_sites_voronoi"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"'{table_name}' data already exists in the database.")
    else:
        # Get the boundary of New Zealand
        nz_boundary = get_nz_boundary(engine, to_crs=4326)
        # Get all rainfall sites within the boundary of New Zealand from the database
        sites_in_nz = get_sites_within_aoi(engine, nz_boundary)
        # Calculate the Thiessen polygons, i.e. the area covered by each rainfall site
        log.info(f"Calculating '{table_name}'.")
        rainfall_sites_voronoi = thiessen_polygons_calculator(nz_boundary, sites_in_nz)
        # Store the Thiessen polygons data in the database
        log.info(f"Adding '{table_name}' data to the database.")
        rainfall_sites_voronoi.to_postgis(f"{table_name}", engine, if_exists="replace")


def thiessen_polygons_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get rainfall sites coverage areas (Thiessen polygons) that intersect or are within the catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the rainfall sites coverage areas (Thiessen polygons) that intersect or
        are within the catchment area.
    """
    # Extract the geometry of the catchment area
    catchment_polygon = catchment_area["geometry"].iloc[0]
    # Construct the query to get rainfall sites coverage areas (Thiessen polygons)
    command_text = """
    SELECT *
    FROM rainfall_sites_voronoi AS rsv
    WHERE ST_Intersects(rsv.geometry, ST_GeomFromText(:catchment_polygon, 4326));
    """
    query = text(command_text).bindparams(
        catchment_polygon=str(catchment_polygon)
    )
    # Retrieve the data from the database
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(
        query,
        engine,
        geom_col="geometry", crs=4326
    )
    # Reset the index
    sites_in_catchment.reset_index(drop=True, inplace=True)
    return sites_in_catchment
