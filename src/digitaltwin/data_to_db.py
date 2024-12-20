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
This script fetches geospatial data from various providers using the 'geoapis' library and stores it in the database.
It also saves user log information in the database.
"""

import logging
from typing import Tuple, Set

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.digitaltwin.tables import GeospatialLayers, UserLogInfo, create_table, check_table_exists, execute_query
from src.digitaltwin.get_data_using_geoapis import fetch_vector_data_using_geoapis

log = logging.getLogger(__name__)


class NoNonIntersectionError(Exception):
    """Exception raised when no non-intersecting area is found."""
    pass


def get_nz_geospatial_layers(engine: Engine) -> pd.DataFrame:
    """
    Retrieve geospatial layers from the database that have a coverage area of New Zealand.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing geospatial layers that have a coverage area of New Zealand.
    """
    # SQL query to retrieve geospatial layers that have a coverage area of New Zealand
    nz_geo_query = f"""
    SELECT *
    FROM {GeospatialLayers.__tablename__}
    WHERE coverage_area = 'New Zealand' AND unique_column_name IS NULL;
    """
    # Retrieve geospatial layers using the provided SQL query
    nz_geo_layers = pd.read_sql(nz_geo_query, engine)
    # Drop the 'unique_id' column from the DataFrame
    nz_geo_layers = nz_geo_layers.drop(columns=['unique_id'])
    return nz_geo_layers


def get_non_nz_geospatial_layers(engine: Engine) -> pd.DataFrame:
    """
    Retrieve geospatial layers from the database that do not have a coverage area of New Zealand.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing geospatial layers that do not have a coverage area of New Zealand.
    """
    # SQL query to retrieve geospatial layers that do not have coverage area of New Zealand
    non_nz_query = f"""
    SELECT *
    FROM {GeospatialLayers.__tablename__}
    WHERE unique_column_name IS NOT NULL AND (coverage_area != 'New Zealand' OR coverage_area IS NULL);
    """
    # Retrieve geospatial layers using the provided SQL query
    non_nz_geo_layers = pd.read_sql(non_nz_query, engine)
    # Drop the 'unique_id' column from the DataFrame
    non_nz_geo_layers = non_nz_geo_layers.drop(columns=['unique_id'])
    return non_nz_geo_layers


def get_geospatial_layer_info(layer_row: pd.Series) -> Tuple[str, int, str, str]:
    """
    Extracts geospatial layer information from a single layer entry.

    Parameters
    ----------
    layer_row : pd.Series
        A geospatial layer row that represents a single geospatial layer along with its associated information.

    Returns
    -------
    Tuple[str, int, str, str]
        A tuple containing the values for data_provider, layer_id, table_name, and unique_column_name.
    """
    # Extract information from the single layer entry
    data_provider = layer_row['data_provider']
    layer_id = layer_row['layer_id']
    table_name = layer_row["table_name"]
    unique_column_name = layer_row['unique_column_name']
    return data_provider, layer_id, table_name, unique_column_name


def get_vector_data_id_not_in_db(
        engine: Engine,
        vector_data: gpd.GeoDataFrame,
        table_name: str,
        unique_column_name: str,
        area_of_interest: gpd.GeoDataFrame) -> Set[int]:
    """
    Get the IDs from the fetched vector_data that are not present in the specified database table
    for the area of interest.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    vector_data : gpd.GeoDataFrame
        A GeoDataFrame containing the fetched vector data.
    table_name : str
        The name of the table in the database.
    unique_column_name : str
        The name of the unique column in the table.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.

    Returns
    -------
    Set[int]
        The set of IDs from the fetched vector_data that are not present in the specified table in the database.
    """
    # Get the unique IDs from the vector_data
    vector_data_ids = set(vector_data[unique_column_name])
    # Fetch the unique IDs from the specified table that intersect with the area of interest
    aoi_polygon = area_of_interest["geometry"][0]
    command_text = f"""
    SELECT DISTINCT {unique_column_name}
    FROM {table_name} AS ids
    WHERE ST_Intersects(ids.geometry, ST_GeomFromText(:aoi_polygon, 2193));
    """
    query = text(command_text).bindparams(
        aoi_polygon=str(aoi_polygon)
    )
    # Execute the query and retrieve the IDs present in the database
    ids_in_db = set(pd.read_sql(query, engine)[unique_column_name])
    # Find the IDs from vector_data that are not present in the database
    ids_not_in_db = vector_data_ids - ids_in_db
    return ids_not_in_db


def nz_geospatial_layers_data_to_db(
        engine: Engine,
        crs: int = 2193,
        verbose: bool = False) -> None:
    """
    Fetches New Zealand geospatial layers data using 'geoapis' and stores it into the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    crs : int = 2193
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool = False
        Whether to print messages. Default is False.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get New Zealand geospatial layers
    nz_geo_layers = get_nz_geospatial_layers(engine)

    # Iterate over each NZ geospatial layer
    for _, layer_row in nz_geo_layers.iterrows():
        # Extract geospatial layer information
        data_provider, layer_id, table_name, _ = get_geospatial_layer_info(layer_row)

        # Check if the table already exists in the database
        if check_table_exists(engine, table_name):
            log.info(f"'{table_name}' data already exists in the database.")
        else:
            # Fetch vector data using geoapis
            log.info(f"Fetching '{table_name}' data ({data_provider} {layer_id}).")
            vector_data = fetch_vector_data_using_geoapis(data_provider, layer_id, crs, verbose)
            # Insert vector data into the database
            log.info(f"Adding '{table_name}' data ({data_provider} {layer_id}) to the database.")
            vector_data.to_postgis(table_name, engine, index=False, if_exists="replace")


def get_non_intersection_area_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        table_name: str) -> gpd.GeoDataFrame:
    """
    Get the non-intersecting area from the catchment area and user log information table in the database
    for the specified table.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    table_name : str
        The name of the table in the database.

    Returns
    -------
    gpd.GeoDataFrame
        The non-intersecting area, or the original catchment area if no intersections are found.

    Raises
    ------
    NoNonIntersectionError
        If the non-intersecting area is empty, it suggests that the catchment area is already fully covered.
    """
    # Create the 'user_log_information' table if it doesn't exist
    create_table(engine, UserLogInfo)
    # Extract the geometry of the catchment area
    catchment_polygon = catchment_area["geometry"][0]
    # Build the SQL query to find intersections between the user log information and the catchment area
    command_text = f"""
    SELECT *
    FROM (
        SELECT *
        FROM {UserLogInfo.__tablename__}
        WHERE :table_name = ANY(source_table_list)
    ) AS sub
    WHERE ST_Intersects(sub.geometry, ST_GeomFromText(:catchment_polygon, 2193));
    """
    query = text(command_text).bindparams(
        table_name=str(table_name),
        catchment_polygon=str(catchment_polygon)
    )
    # Execute the SQL query and retrieve the intersections as a GeoDataFrame
    user_log_intersections = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Check if there are no intersections
    if user_log_intersections.empty:
        return catchment_area
    # Compute the non-intersecting area by overlaying the catchment area with the intersections
    non_intersection_area = catchment_area.overlay(user_log_intersections, how='difference')
    # Check if the non-intersecting area is empty
    if non_intersection_area.empty:
        raise NoNonIntersectionError(
            f"'{table_name}' data for the requested catchment area is already in the database.")
    else:
        return non_intersection_area


def process_new_non_nz_geospatial_layers(
        engine: Engine,
        data_provider: str,
        layer_id: int,
        table_name: str,
        area_of_interest: gpd.GeoDataFrame,
        crs: int = 2193,
        verbose: bool = False) -> None:
    """
    Fetches new non-NZ geospatial layers data using 'geoapis' and stores it into the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    data_provider : str
        The data provider of the geospatial layer.
    layer_id : int
        The ID of the geospatial layer.
    table_name : str
        The database table name of the geospatial layer.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.
    crs : int = 2193
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool = False
        Whether to print messages. Default is False.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Fetch vector data using geoapis
    log.info(f"Fetching '{table_name}' data ({data_provider} {layer_id}) for the catchment area.")
    vector_data = fetch_vector_data_using_geoapis(data_provider, layer_id, crs, verbose, area_of_interest)
    # Check if the fetched vector data is empty
    if vector_data.empty:
        log.info(f"The requested catchment area does not contain any '{table_name}' data ({data_provider} {layer_id}).")
    else:
        # Insert vector data into the database
        log.info(f"Adding '{table_name}' data ({data_provider} {layer_id}) for the catchment area to the database.")
        vector_data.to_postgis(table_name, engine, index=False, if_exists="replace")


def process_existing_non_nz_geospatial_layers(
        engine: Engine,
        data_provider: str,
        layer_id: int,
        table_name: str,
        unique_column_name: str,
        area_of_interest: gpd.GeoDataFrame,
        crs: int = 2193,
        verbose: bool = False) -> None:
    """
    Fetches existing non-NZ geospatial layers data using 'geoapis' and stores it into the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    data_provider : str
        The data provider of the geospatial layer.
    layer_id : int
        The ID of the geospatial layer.
    table_name : str
        The database table name of the geospatial layer.
    unique_column_name : str
        The unique column name used for record identification in the database table.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.
    crs : int = 2193
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool = False
        Whether to print messages. Default is False.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Fetch vector data using geoapis
    log.info(f"Fetching '{table_name}' data ({data_provider} {layer_id}) for the catchment area.")
    vector_data = fetch_vector_data_using_geoapis(data_provider, layer_id, crs, verbose, area_of_interest)
    # Check if the fetched vector data is empty
    if vector_data.empty:
        log.info(f"The requested catchment area does not contain any '{table_name}' data ({data_provider} {layer_id}).")
    else:
        # Get IDs from the vector data that are not in the database
        ids_not_in_db = get_vector_data_id_not_in_db(
            engine, vector_data, table_name, unique_column_name, area_of_interest)
        # Check if there are IDs not in the database
        if ids_not_in_db:
            # Get vector data that contains only the IDs not present in the database
            vector_data_not_in_db = vector_data[vector_data[unique_column_name].isin(ids_not_in_db)]
            # Insert vector data into the database
            log.info(
                f"Adding new '{table_name}' data ({data_provider} {layer_id}) for the catchment area to the database.")
            vector_data_not_in_db.to_postgis(table_name, engine, index=False, if_exists="append")
        else:
            log.info(f"'{table_name}' data for the requested catchment area is already in the database.")


def non_nz_geospatial_layers_data_to_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        crs: int = 2193,
        verbose: bool = False) -> None:
    """
    Fetches non-NZ geospatial layers data using 'geoapis' and stores it into the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    crs : int = 2193
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool = False
        Whether to print messages. Default is False.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get non-NZ geospatial layers from the database
    non_nz_geo_layers = get_non_nz_geospatial_layers(engine)

    # Iterate over each non-NZ geospatial layer
    for _, layer_row in non_nz_geo_layers.iterrows():
        # Extract geospatial layer information
        data_provider, layer_id, table_name, unique_column_name = get_geospatial_layer_info(layer_row)
        try:
            # Get the non-intersection area of the catchment area
            non_intersection_area = get_non_intersection_area_from_db(engine, catchment_area, table_name)
        except NoNonIntersectionError as error:
            # Log the error and continue to the next layer
            log.info(error)
            continue

        # Check if the table already exists in the database
        if check_table_exists(engine, table_name):
            # Process existing non-NZ geospatial layers
            process_existing_non_nz_geospatial_layers(
                engine, data_provider, layer_id, table_name, unique_column_name, non_intersection_area, crs, verbose)
        else:
            # Process new non-NZ geospatial layers
            process_new_non_nz_geospatial_layers(
                engine, data_provider, layer_id, table_name, non_intersection_area, crs, verbose)


def store_geospatial_layers_data_to_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        crs: int = 2193,
        verbose: bool = False) -> None:
    """
    Fetches geospatial layers data using 'geoapis' and stores it into the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    crs : int = 2193
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool = False
        Whether to print messages. Default is False.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Store New Zealand geospatial layers data to the database
    nz_geospatial_layers_data_to_db(engine, crs, verbose)
    # Store non-NZ geospatial layers data to the database
    non_nz_geospatial_layers_data_to_db(engine, catchment_area, crs, verbose)


def user_log_info_to_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> None:
    """
    Store user log information to the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Create the 'user_log_information' table if it doesn't exist
    create_table(engine, UserLogInfo)
    # Get the list of table names for non-NZ geospatial layers
    non_nz_geo_layers = get_non_nz_geospatial_layers(engine)
    table_list = non_nz_geo_layers["table_name"].tolist()
    # Get the catchment geometry
    catchment_geom = catchment_area["geometry"].to_wkt().iloc[0]
    # Create the query object
    query = UserLogInfo(source_table_list=table_list, geometry=catchment_geom)
    # Execute the query
    execute_query(engine, query)
