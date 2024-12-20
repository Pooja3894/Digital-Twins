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
Fetch REC data in New Zealand from NIWA using the ArcGIS REST API.
"""

import asyncio
import logging
from typing import List, Dict, Union, NamedTuple

import aiohttp
import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString
from sqlalchemy.engine import Engine

from src.digitaltwin.utils import get_nz_boundary

log = logging.getLogger(__name__)

# URL for retrieving REC data from NIWA using the ArcGIS REST API
REC_API_URL = "https://gis.niwa.co.nz/server/rest/services/HYDRO/Flood_Statistics_Henderson_Collins_V2/MapServer/2"


class RecordCounts(NamedTuple):
    """
    Represents the record counts of the REC feature layer.

    Attributes
    ----------
    max_record_count : int
        The maximum number of records that will be returned per query.
    total_record_count : int
        The total number of records available in the feature layer.
    """
    max_record_count: int
    total_record_count: int


def get_feature_layer_record_counts(url: str = REC_API_URL) -> RecordCounts:
    """
    Retrieves the maximum and total record counts from the REC feature layer.

    Parameters
    ----------
    url : str = REC_API_URL
        The URL of the REC feature layer. Defaults to `REC_API_URL`.

    Returns
    -------
    RecordCounts
        A named tuple containing the maximum and total record counts of the REC feature layer.
    """
    # Set up parameters for the initial request to get the maximum record count
    params = {"f": "json"}
    response = requests.get(url=url, params=params)
    # Extract the maximum record count from the response
    max_record_count = response.json()["maxRecordCount"]
    # Set up parameters for the second request to get the total record count
    params["where"] = "1=1"
    params["returnCountOnly"] = True
    response = requests.get(url=f"{url}/query", params=params)
    try:
        # Extract the total record count from the response
        total_record_count = response.json()["count"]
    except KeyError as e:
        # Raise a RuntimeError to indicate the API failure
        raise RuntimeError("Failed to fetch rec data feature layer record counts.") from e
    # Returns the maximum and total record counts of the REC feature layer
    return RecordCounts(max_record_count, total_record_count)


def gen_rec_query_param_list(
        engine: Engine,
        max_record_count: int,
        total_record_count: int) -> List[Dict[str, Union[str, int]]]:
    """
    Generate a list of API query parameters used to retrieve REC data in New Zealand.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    max_record_count : int
        The maximum number of records that will be returned per query.
    total_record_count : int
        The total number of records available in the feature layer.

    Returns
    -------
    List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve REC data in New Zealand.
    """
    # Get the New Zealand boundary geometry in the specified CRS
    nz_boundary = get_nz_boundary(engine, to_crs=2193)
    # Extract the bounding box coordinates from the New Zealand boundary
    x_min, y_min, x_max, y_max = nz_boundary.total_bounds
    # Create a string representation of the bounding box coordinates for use in the API query
    nz_geometry = f"{x_min},{y_min},{x_max},{y_max}"

    # Initialize an empty list to store query parameters
    query_param_list = []
    # Use a while loop to generate query parameters in batches
    result_offset = 0
    while result_offset < total_record_count:
        # Define the query parameters for the current batch
        query_params = {
            "where": "1=1",
            "outFields": "*",
            "geometry": nz_geometry,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 2193,
            "spatialRel": "esriSpatialRelContains",
            "outSR": 2193,
            "f": "json",
            "resultOffset": result_offset
        }
        # Append the current batch of query parameters to the list
        query_param_list.append(query_params)
        # Increment 'result_offset' for the next batch
        result_offset += max_record_count
    # Return the list of query parameters
    return query_param_list


async def fetch_rec_data(
        session: aiohttp.ClientSession,
        query_param: Dict[str, Union[str, int]],
        url: str = f"{REC_API_URL}/query") -> gpd.GeoDataFrame:
    """
    Fetch REC data using the provided query parameters within a single API call.

    Parameters
    ----------
    session : aiohttp.ClientSession
        An instance of `aiohttp.ClientSession` used for making HTTP requests.
    query_param : Dict[str, Union[str, int]]
        The query parameters used to retrieve REC data.
    url : str = REC_API_URL
        The query URL of the REC feature layer.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC data.
    """
    # Send a GET request to the provided query URL with the query parameters
    async with session.get(url, params=query_param) as resp:
        # Process the response as JSON
        resp_dict = await resp.json(content_type=None)
        # Extract the features from the response
        features = resp_dict["features"]
        # Create a Pandas DataFrame from the attributes of each feature in the response
        rec_features = pd.DataFrame([feature['attributes'] for feature in features])
        # Extract the geometries from the response and create a list of LineString objects
        rec_geometries = [LineString(feature['geometry']['paths'][0]) for feature in features]
        # Create a GeoDataFrame with REC features and geometries, with specified CRS
        rec_data = gpd.GeoDataFrame(rec_features, geometry=rec_geometries, crs=resp_dict['spatialReference']['wkid'])
        # Return the GeoDataFrame containing REC data
        return rec_data


async def fetch_rec_data_for_nz(
        query_param_list: List[Dict[str, Union[str, int]]],
        url: str = REC_API_URL) -> gpd.GeoDataFrame:
    """
    Iterate over the list of API query parameters to fetch REC data in New Zealand.

    Parameters
    ----------
    query_param_list : List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve REC data in New Zealand.
    url : str = REC_API_URL
        The URL of the REC feature layer. Defaults to `REC_API_URL`.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC data in New Zealand.
    """
    async with aiohttp.ClientSession() as session:
        # Construct the query URL for the REC feature layer
        query_url = f"{url}/query"
        # Create a list of tasks to fetch REC data for each query parameter
        tasks = [fetch_rec_data(session, query_param, query_url) for query_param in query_param_list]
        # Wait for all tasks to complete and retrieve the results
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        # Concatenate the results into a single GeoDataFrame
        rec_data = gpd.GeoDataFrame(pd.concat(query_results))
        # Convert all column names to lowercase
        rec_data.columns = rec_data.columns.str.lower()
        # Remove duplicate records based on the 'objectid' column, preserving the first occurrence
        rec_data = rec_data.drop_duplicates(subset='objectid', keep='first')
        # Sort the GeoDataFrame by the 'objectid' column and reset the index
        rec_data = rec_data.sort_values(by=['objectid']).reset_index(drop=True)
    return rec_data


def fetch_rec_data_from_niwa(engine: Engine, url: str = REC_API_URL) -> gpd.GeoDataFrame:
    """
    Retrieve REC data in New Zealand from NIWA using the ArcGIS REST API.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    url : str = REC_API_URL
        The URL of the REC feature layer. Defaults to `REC_API_URL`.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC data in New Zealand.

    Raises
    ------
    RuntimeError
        If failed to fetch REC data.
    """
    # Retrieves the maximum and total record counts from the REC feature layer
    max_record_count, total_record_count = get_feature_layer_record_counts(url)
    # Generate a list of API query parameters used to retrieve REC data in New Zealand
    query_param_list = gen_rec_query_param_list(engine, max_record_count, total_record_count)
    try:
        # Log that the fetching of REC data has started
        log.info("Fetching 'rec_data' from NIWA using the ArcGIS REST API.")
        # Iterate over the list of API query parameters to fetch REC data in New Zealand
        rec_data = asyncio.run(fetch_rec_data_for_nz(query_param_list, url))
        # Log that the REC data has been successfully fetched
        log.info("Successfully fetched 'rec_data' from NIWA using the ArcGIS REST API.")
        return rec_data
    except TypeError:
        # Raise a RuntimeError to indicate the failure
        raise RuntimeError("Failed to fetch 'rec_data' from NIWA using the ArcGIS REST API.")


def fetch_backup_rec_data_from_niwa() -> gpd.GeoDataFrame:
    """
    Retrieve REC data in New Zealand from NIWA OpenData.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC data in New Zealand.
    """
    # Log a message indicating the start of fetching process
    log.info("Fetching backup 'rec_data' from NIWA OpenData.")
    # URL for the GeoJSON REC data
    url = ("https://opendata.arcgis.com/api/v3/datasets/ae4316ef6bc842c4aed6a76b10b0c39e_2/downloads/data?"
           "format=geojson&spatialRefId=4326&where=1%3D1")
    # Send a GET request to the URL
    response = requests.get(url)
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        geojson_data = response.json()
        # Convert GeoJSON data to GeoDataFrame
        rec_data = gpd.GeoDataFrame.from_features(geojson_data['features'])
        # Ensure consistent column naming convention by converting all column names to lowercase
        rec_data.columns = rec_data.columns.str.lower()
        # Move the 'geometry' column to the end, ensuring spatial columns are located at the end of database tables
        rec_data['geometry'] = rec_data.pop('geometry')
        # Log a message indicating successful fetching
        log.info("Successfully fetched backup 'rec_data' from NIWA OpenData.")
        return rec_data
    else:
        # Raise a RuntimeError if fetching failed
        raise RuntimeError("Failed to fetch backup 'rec_data' from NIWA OpenData.")
