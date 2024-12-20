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
This script handles storing REC data in the database, and retrieving REC data enriched with sea-draining catchment
information from the database.
"""

import logging

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.digitaltwin.tables import check_table_exists
from src.dynamic_boundary_conditions.river import river_data_from_niwa
from src.dynamic_boundary_conditions.river.river_network_to_from_db import add_network_exclusions_to_db

log = logging.getLogger(__name__)


def store_rec_data_to_db(engine: Engine) -> None:
    """
    Store REC data in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Define the table name for storing the REC data
    table_name = "rec_data"
    # Check if the table already exists in the database
    if check_table_exists(engine, table_name):
        log.info(f"'{table_name}' already exists in the database.")
    else:
        try:
            # Retrieve REC data from NIWA using the ArcGIS REST API
            rec_data = river_data_from_niwa.fetch_rec_data_from_niwa(engine)
        except RuntimeError as error:
            # Log a warning message to indicate that a runtime error occurred while fetching REC data
            log.warning(error)
            # Retrieve backup REC data from NIWA OpenData
            rec_data = river_data_from_niwa.fetch_backup_rec_data_from_niwa()
        # Store the REC data to the database table
        log.info(f"Adding '{table_name}' to the database.")
        rec_data.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info(f"Successfully added '{table_name}' to the database.")


def get_sdc_data_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve sea-draining catchment data from the database that intersects with the given catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing sea-draining catchment data that intersects with the given catchment area.
    """
    # Extract the geometry of the catchment area
    catchment_polygon = catchment_area["geometry"][0]
    # Query to retrieve sea-draining catchments that intersect with the catchment polygon
    command_text = """
    SELECT *
    FROM sea_draining_catchments AS sdc
    WHERE ST_Intersects(sdc.geometry, ST_GeomFromText(:catchment_polygon, 2193));
    """
    sea_drain_query = text(command_text).bindparams(
        catchment_polygon=str(catchment_polygon)
    )
    # Execute the query and create a GeoDataFrame from the result
    sdc_data = gpd.GeoDataFrame.from_postgis(sea_drain_query, engine, geom_col="geometry")
    return sdc_data


def get_rec_data_with_sdc_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        river_network_id: int) -> gpd.GeoDataFrame:
    """
    Retrieve REC data from the database for the specified catchment area with an additional column that identifies
    the associated sea-draining catchment for each REC geometry.
    Simultaneously, identify the REC geometries that do not fully reside within sea-draining catchments and
    proceed to add these excluded REC geometries to the appropriate database table.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    river_network_id : int
        An identifier for the river network associated with the current run.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved REC data for the specified catchment area with an additional column
        that identifies the associated sea-draining catchment for each REC geometry.
    """
    # Get sea-draining catchment data from the database
    sdc_data = get_sdc_data_from_db(engine, catchment_area)
    # Unify the sea-draining catchment polygons into a single polygon
    sdc_polygon = sdc_data.unary_union
    # Create a GeoDataFrame representing the unified sea-draining catchment area
    sdc_area = gpd.GeoDataFrame(geometry=[sdc_polygon], crs=sdc_data.crs)
    # Combine the sea-draining catchment area with the input catchment area to create a final unified polygon
    combined_polygon = pd.concat([sdc_area, catchment_area]).unary_union
    # Query to retrieve REC data that intersects with the combined polygon
    command_text = """
    SELECT *
    FROM rec_data AS rec
    WHERE ST_Intersects(rec.geometry, ST_GeomFromText(:combined_polygon, 2193));
    """
    rec_query = text(command_text).bindparams(
        combined_polygon=str(combined_polygon)
    )
    # Execute the query and retrieve the REC data from the database
    rec_data = gpd.GeoDataFrame.from_postgis(rec_query, engine, geom_col="geometry")
    # Determine the sea-draining catchment for each REC geometry (using the 'within' predicate)
    rec_data_join_sdc = (
        gpd.sjoin(rec_data, sdc_data[["catch_id", "geometry"]], how="left", predicate="within")
        .drop(columns=["index_right"])
    )
    # Get rows where REC geometries are fully contained within sea-draining catchments
    rec_data_with_sdc = rec_data_join_sdc[~rec_data_join_sdc["catch_id"].isna()]
    # Remove any duplicate records and sort by the 'objectid' column
    rec_data_with_sdc = rec_data_with_sdc.drop_duplicates().sort_values(by="objectid").reset_index(drop=True)
    # Convert the 'catch_id' column to integers
    rec_data_with_sdc["catch_id"] = rec_data_with_sdc["catch_id"].astype(int)
    # Get the object IDs of REC geometries that are not fully contained within sea-draining catchments
    rec_network_exclusions = rec_data_join_sdc[rec_data_join_sdc["catch_id"].isna()].reset_index(drop=True)
    # Add excluded REC geometries in the River Network to the relevant database table
    add_network_exclusions_to_db(engine, river_network_id, rec_network_exclusions,
                                 exclusion_cause="crossing multiple sea-draining catchments")
    return rec_data_with_sdc
