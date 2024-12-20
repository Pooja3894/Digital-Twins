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
Store the rainfall data for all the sites within the catchment area in the database.
"""

import logging
from typing import List

import pandas as pd
import geopandas as gpd
from sqlalchemy.engine import Engine

from src.digitaltwin import tables
from src.dynamic_boundary_conditions.rainfall import rainfall_data_from_hirds

log = logging.getLogger(__name__)


def db_rain_table_name(idf: bool) -> str:
    """
    Return the relevant rainfall data table name used in the database.

    Parameters
    ----------
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.

    Returns
    -------
    str
        The relevant rainfall data table name.
    """
    # Determine the table name based on the idf parameter
    table_name = "rainfall_depth" if idf is False else "rainfall_intensity"
    return table_name


def get_site_ids_in_catchment(sites_in_catchment: gpd.GeoDataFrame) -> List[str]:
    """
    Get the rainfall site IDs within the catchment area.

    Parameters
    ----------
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (Thiessen polygons) that intersect or are within the catchment area.

    Returns
    -------
    List[str]
        The rainfall site IDs within the catchment area.
    """
    # Extract the site IDs from the "site_id" column of the sites_in_catchment GeoDataFrame
    site_ids_in_catchment = sites_in_catchment["site_id"].tolist()
    return site_ids_in_catchment


def get_site_ids_not_in_db(engine: Engine, site_ids_in_catchment: List[str], idf: bool) -> List[str]:
    """
    Get the list of rainfall site IDs that are within the catchment area but not in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    site_ids_in_catchment : List[str]
        Rainfall site IDs within the catchment area.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.

    Returns
    -------
    List[str]
        The rainfall site IDs within the catchment area but not present in the database.
    """
    # Get the relevant rainfall data table name from the idf parameter
    rain_table_name = db_rain_table_name(idf)
    # Construct the query to retrieve the distinct site IDs from the rainfall data table
    query = f"SELECT DISTINCT site_id FROM {rain_table_name};"
    # Execute the query and retrieve the site IDs in the database as a DataFrame
    site_ids_in_db = pd.read_sql_query(query, engine)
    # Convert the DataFrame to a list of site IDs in the database
    site_ids_in_db = site_ids_in_db["site_id"].tolist()
    # Find the site IDs in site_ids_in_catchment that are not present in site_ids_in_db
    site_ids_not_in_db = list(set(site_ids_in_catchment).difference(site_ids_in_db))
    return site_ids_not_in_db


def add_rainfall_data_to_db(engine: Engine, site_id: str, idf: bool) -> None:
    """
    Store the rainfall data for a specific site in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    site_id : str
        HIRDS rainfall site ID.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get the relevant rainfall data table name from the idf parameter
    rain_table_name = db_rain_table_name(idf)
    # Retrieve the rainfall data for the specified site from HIRDS
    log.info(f"Fetching '{rain_table_name}' data for site {site_id} from the HIRDS website https://hirds.niwa.co.nz/.")
    site_data = rainfall_data_from_hirds.get_data_from_hirds(site_id, idf)
    # Extract the layout structure of the data
    layout_structure = rainfall_data_from_hirds.get_layout_structure_of_data(site_data)

    log.info(f"Adding '{rain_table_name}' data for site {site_id} to the database.")
    # Iterate over each block structure in the layout structure
    for block_structure in layout_structure:
        # Convert the data to a tabular format
        rain_data = rainfall_data_from_hirds.convert_to_tabular_data(site_data, site_id, block_structure)
        # Store the tabular data in the relevant rainfall data table in the database
        rain_data.to_sql(rain_table_name, engine, index=False, if_exists="append")


def add_each_site_rainfall_data(engine: Engine, site_ids_list: List[str], idf: bool) -> None:
    """
    Add rainfall data for each site in the site_ids_list to the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    site_ids_list : List[str]
        List of rainfall sites' IDs.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.

    Returns
    -------
    None
        This function does not return any value.
    """
    for site_id in site_ids_list:
        add_rainfall_data_to_db(engine, site_id, idf)


def rainfall_data_to_db(engine: Engine, sites_in_catchment: gpd.GeoDataFrame, idf: bool = False) -> None:
    """
    Store rainfall data of all the sites within the catchment area in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (Thiessen polygons) that intersect or are within the catchment area.
    idf : bool = False
        Set to False for rainfall depth data, and True for rainfall intensity data.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get the IDs of the sites within the catchment area
    site_ids_in_catchment = get_site_ids_in_catchment(sites_in_catchment)
    # Determine the table name based on idf
    table_name = db_rain_table_name(idf)
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        # Get the IDs of sites not in the database
        site_ids_not_in_db = get_site_ids_not_in_db(engine, site_ids_in_catchment, idf)
        # Check if there are sites not in the database
        if site_ids_not_in_db:
            # Add rainfall data for sites not in the database
            add_each_site_rainfall_data(engine, site_ids_not_in_db, idf)
        else:
            log.info(f"'{table_name}' data for sites within the requested catchment area is already in the database.")
    else:
        # Check if there are sites within the catchment area
        if site_ids_in_catchment:
            # Add rainfall data for all sites within the catchment area
            add_each_site_rainfall_data(engine, site_ids_in_catchment, idf)
        else:
            log.info("No rainfall sites found within the requested catchment area.")
