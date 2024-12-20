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
This script handles the downloading and reading of sea level rise data from the NZ Sea level rise datasets,
storing the data in the database, and retrieving the closest sea level rise data from the database for all locations
in the provided tide data.
"""  # noqa: D400

from io import StringIO
import logging
import pathlib
from typing import Dict

import geopandas as gpd
import pandas as pd
import requests
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.digitaltwin import tables

log = logging.getLogger(__name__)


def modify_slr_data_from_takiwa(slr_nz_dict: Dict[str, pd.DataFrame]) -> gpd.GeoDataFrame:
    """
    Modify sea level rise data stored under dictionary to a GeoDataFrame and return.

    Parameters
    ----------
    slr_nz_dict : Dict[str, pd.DataFrame]
        A dictionary containing the sea level rise data from the NZ Sea level rise datasets.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise data from the NZ Sea level rise datasets.
    """
    # Create a copy dataframe for NZ_VLM_final_May24
    slr_nz = slr_nz_dict["NZ_VLM_final_May24"].copy(deep=True)
    # Merge Site Details dataframe and Sea level projections tables WITH and WITHOUT VLM
    slr_nz_merge_list = []
    for vlm_name in ["NZSeaRise_proj_vlm", "NZSeaRise_proj_novlm"]:
        slr_nz_merge = slr_nz.merge(
            slr_nz_dict[vlm_name],
            left_on='Site ID',
            right_on='site',
            how='left'
        )
        slr_nz_merge['add_vlm'] = True if vlm_name == "NZSeaRise_proj_vlm" else False
        slr_nz_merge_list.append(slr_nz_merge)
    # Concatenate all the dataframes (both WITH VLM and WITHOUT VLM)
    slr_nz_df = pd.concat([slr_nz_merge_list[0], slr_nz_merge_list[1]], axis=0).reset_index(drop=True)

    # Remove unnamed columns
    slr_nz_df = slr_nz_df.loc[:, ~slr_nz_df.columns.str.contains('^Unnamed')]
    # Remove site column
    slr_nz_df = slr_nz_df.drop(columns=['site'])
    # Rename the columns
    slr_nz_df = slr_nz_df.rename(columns={
        'Site ID': 'siteid',
        'Lon': 'lon',
        'Lat': 'lat',
        'Vertical Rate (mm/yr)': 'vertical_rate',
        'Vertical Rate - BOP corrected (mm/yr)': 'vertical_rate_bop',
        '1-sigma uncertainty (mm/yr)': 'sigma_uncertainty',
        'Number of obs': 'number_of_obs',
        'Quality Factor': 'quality_factor',
        'Average distance between coastal point and observations': "average_distance",
        'Confidence': 'confidence_level',
        '0.17': 'p17',
        '0.5': 'p50',
        '0.83': 'p83',
        'SSP': 'ssp'
    })

    # Remove '_confidence' in confidence_level column
    slr_nz_df['confidence_level'] = slr_nz_df['confidence_level'].str.split('_').str[0]

    # Add geometry
    geometry = gpd.points_from_xy(slr_nz_df['lon'], slr_nz_df['lat'], crs=4326)
    slr_nz_with_geom = gpd.GeoDataFrame(slr_nz_df, geometry=geometry)

    return slr_nz_with_geom


def get_slr_data_from_takiwa() -> gpd.GeoDataFrame:
    """
    Fetch sea level rise data from the NZ SeaRise Takiwa website.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise data from the NZ Sea level rise datasets.
    """
    #  The URL for retrieving the sea level rise files
    url = 'https://zenodo.org/records/11398538/export/json'

    # Log that the fetching of sea level rise data from NZ SeaRise Takiwa has started
    log.info("Fetching 'sea_level_rise' data from NZ SeaRise Takiwa.")

    # Create a dictionary to store the sea level rise dataset
    slr_nz_dict = {}
    # Request export information json from Zenodo
    response = requests.get(url)
    response.raise_for_status()
    export_json = response.json()
    # Get necessary links from json file
    for file_name, file_info in export_json['files']['entries'].items():
        # Get file name without extension
        file_name_without_extension = pathlib.Path(file_name).stem
        # Request csv dataset using requests module, since it does not cause 401 errors like pd.read_csv
        csv_contents_response = requests.get(file_info["links"]["content"])
        # Form into file-like buffer for reading into dataframe
        csv_contents_buffer = StringIO(csv_contents_response.text)
        # Collect sea level rise dataframe and store into dictionary
        slr_nz_dict[file_name_without_extension] = pd.read_csv(csv_contents_buffer)
        # Log that the data has been successfully fetched
        log.info(f"Successfully fetched the '{file_name}' data.")

    # Log that all data have been successfully fetched
    log.info("Successfully fetched all the 'sea_level_rise' data from NZ SeaRise Takiwa.")

    # Edit and convert dictionary into a GeoDataframe
    slr_nz_with_geom = modify_slr_data_from_takiwa(slr_nz_dict)

    return slr_nz_with_geom


def store_slr_data_to_db(engine: Engine) -> None:
    """
    Store sea level rise data to the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    # Define the table name for storing the sea level rise data
    table_name = "sea_level_rise"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"'{table_name}' data already exists in the database.")
    else:
        # Read sea level rise data from the NZ Sea level rise datasets
        slr_nz = get_slr_data_from_takiwa()
        # Store the sea level rise data to the database table
        log.info(f"Adding '{table_name}' data to the database.")
        slr_nz.to_postgis(table_name, engine, index=False, if_exists="replace")


def get_closest_slr_data(engine: Engine, single_query_loc: pd.Series) -> gpd.GeoDataFrame:
    """
    Retrieve the closest sea level rise data for a single query location from the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    single_query_loc : pd.Series
        Pandas Series containing the location coordinate and additional information used for retrieval.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest sea level rise data for the query location from the database.
    """
    # Create a GeoDataFrame with the query location geometry
    query_loc_geom = gpd.GeoDataFrame(geometry=[single_query_loc["geometry"]], crs=4326)
    # Convert the query location geometry to the desired coordinate reference system (CRS)
    query_loc_geom = query_loc_geom.to_crs(2193).reset_index(drop=True)
    # Prepare the query to retrieve sea level rise data based on the query location.
    # The subquery calculates the distances between the query location and each location in the 'sea_level_rise' table.
    # It then identifies the location with the shortest distance, indicating the closest location to the query location,
    # and retrieves the 'siteid' associated with that closest location, along with its corresponding distance value.
    # The outer query joins the sea_level_rise table with the inner subquery, merging the results to retrieve the
    # relevant data, which includes the calculated distance. By matching the closest location's 'siteid' from the
    # inner subquery with the corresponding data in the sea_level_rise table using the JOIN clause, the outer query
    # obtains the sea level rise data for the closest location, along with its associated distance value.
    command_text = """
    SELECT slr.*, distances.distance
    FROM sea_level_rise AS slr
    JOIN (
        SELECT siteid,
        ST_Distance(ST_Transform(geometry, 2193), ST_GeomFromText(:geom, 2193)) AS distance
        FROM sea_level_rise
        ORDER BY distance
        LIMIT 1
    ) AS distances ON slr.siteid = distances.siteid;
    """
    query = text(command_text).bindparams(
        geom=str(query_loc_geom["geometry"][0])
    )
    # Execute the query and retrieve the data as a GeoDataFrame
    query_data = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Add the position information to the retrieved data
    query_data["position"] = single_query_loc["position"]
    return query_data


def get_slr_data_from_db(engine: Engine, tide_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve the closest sea level rise data from the database for all locations in the provided tide data.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    tide_data : gpd.GeoDataFrame
        A GeoDataFrame containing tide data with added time information (seconds, minutes, hours) and location details.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest sea level rise data for all locations in the tide data.
    """
    log.info("Retrieving 'sea_level_rise' data for the requested catchment area from the database.")
    # Select unique query locations from the tide data
    tide_data_loc = tide_data[['position', 'geometry']].drop_duplicates()
    # Initialize an empty GeoDataFrame to store the closest sea level rise data for all locations
    slr_data = gpd.GeoDataFrame()
    # Iterate over each query location
    for _, row in tide_data_loc.iterrows():
        # Retrieve the closest sea level rise data from the database for the current query location
        query_loc_data = get_closest_slr_data(engine, row)
        # Add a column to the retrieved data to store the geometry of the tide data location
        query_loc_data["tide_data_loc"] = row["geometry"]
        # Concatenate the closest sea level rise data for the query location with the overall sea level rise data
        slr_data = pd.concat([slr_data, query_loc_data])
    # Reset the index of the closest sea level rise data
    slr_data = gpd.GeoDataFrame(slr_data).reset_index(drop=True)
    return slr_data
