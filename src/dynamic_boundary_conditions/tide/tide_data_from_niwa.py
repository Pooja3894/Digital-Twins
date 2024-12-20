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
Fetch tide data from NIWA using the Tide API based on the specified approach, datum, etc.
"""

import asyncio
import io
import logging
from datetime import date, timedelta
from math import ceil
from typing import Dict, List, Tuple, Union, Optional

import aiohttp
import geopandas as gpd
import numpy as np
import pandas as pd

from src import config
from src.dynamic_boundary_conditions.tide.tide_enum import DatumType, ApproachType

log = logging.getLogger(__name__)

# URLs for retrieving tide data from the NIWA Tide API in JSON and CSV formats, respectively
TIDE_API_URL_DATA = "https://api.niwa.co.nz/tides/data"
TIDE_API_URL_DATA_CSV = "https://api.niwa.co.nz/tides/data.csv"


def get_query_loc_coords_position(query_loc_row: gpd.GeoDataFrame) -> Tuple[float, float, str]:
    """
    Get the latitude, longitude, and position of a query location.

    Parameters
    ----------
    query_loc_row : gpd.GeoDataFrame
        A GeoDataFrame representing a query location used to fetch tide data from NIWA using the tide API.

    Returns
    -------
    Tuple[float, float, str]
        A tuple containing the latitude, longitude, and position of the query location.
    """
    # Reset the index of the query location GeoDataFrame
    query_loc_row = query_loc_row.reset_index(drop=True)
    # Get the position from the query location GeoDataFrame
    position = query_loc_row['position'][0]
    # Get the query location point
    query_loc_point = query_loc_row['geometry'][0]
    # Get the longitude and latitude from the query location point
    long, lat = query_loc_point.x, query_loc_point.y
    return lat, long, position


def get_date_ranges(
        start_date: date = date.today(),
        total_days: int = 365,
        days_per_call: int = 31) -> Dict[date, int]:
    """
    Get the start date and duration, measured in days, for each API call used to fetch tide data for the
    requested period.

    Parameters
    ----------
    start_date : date = date.today()
        The start date for retrieving tide data. It can be in the past or present. Default is today's date.
    total_days : int = 365
        The total number of days of tide data to retrieve. Default is 365 days (one year).
    days_per_call : int = 31
        The number of days to fetch in each API call. Must be between 1 and 31 inclusive.
        Default is 31, which represents the maximum number of days that can be fetched per API call.

    Returns
    -------
    Dict[date, int]
        A dictionary containing the start date as the key and the duration, in days, for each API call as the value.

    Raises
    ------
    ValueError
        - If 'total_days' is less than 1.
        - If 'days_per_call' is not between 1 and 31 inclusive.
    """
    # Check for invalid arguments
    if total_days < 1:
        raise ValueError(f"total_days is {total_days}, must be at least 1.")
    # Verify that the provided argument meets the query parameter requirements of the Tide API
    if not 1 <= days_per_call <= 31:
        raise ValueError(f"days_per_call is {days_per_call}, must be between 1 and 31 inclusive.")
    # Calculate the end date for retrieving tide data
    end_date = start_date + timedelta(days=total_days - 1)
    # Initialize an empty dictionary to store the date ranges
    date_ranges = {}
    # Loop through the date range, adding each chunk of data to the dictionary
    while start_date <= end_date:
        # Determine the end date of the current chunk
        request_end_date = min(end_date, start_date + timedelta(days=days_per_call - 1))
        # Calculate the number of days in the current chunk
        number_of_days = (request_end_date - start_date).days + 1
        # Add the current chunk to the date_ranges dictionary
        date_ranges[start_date] = number_of_days
        # Move the start date forward for the next chunk
        start_date += timedelta(days=number_of_days)
    return date_ranges


def gen_tide_query_param_list(
        lat: Union[int, float],
        long: Union[int, float],
        date_ranges: Dict[date, int],
        interval_mins: Optional[int] = None,
        datum: DatumType = DatumType.LAT) -> List[Dict[str, Union[str, int]]]:
    """
    Generate a list of API query parameters used to retrieve tide data for the requested period.

    Parameters
    ----------
    lat : Union[int, float]
        Latitude in the range of -29 to -53 (e.g., -30.876).
    long : Union[int, float]
        Longitude in the range of 160 to 180 and -175 to -180 (e.g., -175.543).
    date_ranges : Dict[date, int]
        Dictionary of start date and number of days for each API call needed to retrieve tide data
        for the requested period.
    interval_mins : Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to retrieve only the highest and lowest tide data.
    datum : DatumType = DatumType.LAT
        Datum used for fetching tide data from NIWA. Default value is LAT.
        Valid options are LAT for the Lowest Astronomical Tide and MSL for the Mean Sea Level.

    Returns
    -------
    List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve tide data for the requested period.

    Raises
    ------
    ValueError
        - If the latitude is outside the range of -29 to -53.
        - If the longitude is outside the range of 160 to 180 or -175 to -180.
        - If the time interval is provided and outside the range of 10 to 1440.
    """
    # Verify that the provided arguments meet the query parameter requirements of the Tide API
    if not (-53 <= lat <= -29):
        raise ValueError(f"latitude is {lat}, must range from -29 to -53.")
    if not ((160 <= long <= 180) or (-180 <= long <= -175)):
        raise ValueError(f"longitude is {long}, must range from 160 to 180 or from -175 to -180.")
    if interval_mins is not None and not (10 <= interval_mins <= 1440):
        raise ValueError(f"interval is {interval_mins}, must range from 10 to 1440.")

    # Get the NIWA API key
    niwa_api_key = config.get_env_variable("NIWA_API_KEY")

    # Create an empty list to store the API query parameters
    query_param_list = []
    # Iterate over each item in the 'date_ranges' dictionary
    for start_date, number_of_days in date_ranges.items():
        # Create a dictionary to store the query parameters for the current date range
        query_param = {
            "apikey": niwa_api_key,
            "lat": str(lat),
            "long": str(long),
            "numberOfDays": number_of_days,
            "startDate": start_date.isoformat(),
            "datum": datum.value
        }
        # Check if an interval is provided
        if interval_mins is not None:
            # Add interval to the query parameters
            query_param["interval"] = interval_mins
        # Append the current query parameters to the list
        query_param_list.append(query_param)
    return query_param_list


async def fetch_tide_data(
        session: aiohttp.ClientSession,
        query_param: Dict[str, Union[str, int]],
        url: str = TIDE_API_URL_DATA) -> gpd.GeoDataFrame:
    """
    Fetch tide data using the provided query parameters within a single API call.

    Parameters
    ----------
    session : aiohttp.ClientSession
        An instance of `aiohttp.ClientSession` used for making HTTP requests.
    query_param : Dict[str, Union[str, int]]
        The query parameters used to retrieve tide data for a specific location and time period.
    url : str = TIDE_API_URL_DATA
        Tide API HTTP request URL. Defaults to `TIDE_API_URL_DATA`.
        Can be either `TIDE_API_URL_DATA` or `TIDE_API_URL_DATA_CSV`.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched tide data.
    """
    # Send a GET request to the provided URL with the query parameters
    async with session.get(url, params=query_param) as resp:
        if url == TIDE_API_URL_DATA:
            # Process response as JSON
            resp_dict = await resp.json()
            # Create a DataFrame from the 'values' field of the response dictionary
            tide_df = pd.DataFrame(resp_dict['values'])
            # Insert the 'datum', 'latitude', and 'longitude' columns at specific locations in the DataFrame
            tide_df.insert(loc=0, column='datum', value=resp_dict['metadata']['datum'])
            tide_df.insert(loc=1, column='latitude', value=resp_dict['metadata']['latitude'])
            tide_df.insert(loc=2, column='longitude', value=resp_dict['metadata']['longitude'])
        else:
            # Process response as text
            resp_text = await resp.text()
            # Read the response text as a CSV into a DataFrame and reset the index
            data = pd.read_csv(io.StringIO(resp_text)).reset_index()
            # Find the index of the row containing the header 'TIME'
            header_index = data[data['index'] == 'TIME'].index[0]
            # Extract the rows starting from the row after the header row and reset the index
            tide_df = data[header_index + 1:].reset_index(drop=True)
            # Convert the header names to lowercase for consistency
            tide_df.columns = [header.lower() for header in data.iloc[header_index].tolist()]
            # Convert the 'value' column to float data type
            tide_df['value'] = tide_df['value'].astype(float)
            # Insert the 'datum', 'latitude', and 'longitude' columns at specific locations in the DataFrame
            tide_df.insert(loc=0, column='datum', value=data[data['index'] == 'Datum'].values[0][1].strip())
            tide_df.insert(loc=1, column='latitude', value=float(data[data['index'] == 'Latitude'].values[0][1]))
            tide_df.insert(loc=2, column='longitude', value=float(data[data['index'] == 'Longitude'].values[0][1]))
        # Create a geometry column based on longitude and latitude coordinates
        geometry = gpd.points_from_xy(tide_df['longitude'], tide_df['latitude'])
        # Convert the DataFrame to a GeoDataFrame by adding geometry column and setting CRS
        tide_df = gpd.GeoDataFrame(tide_df, geometry=geometry, crs=4326)
        return tide_df


async def fetch_tide_data_for_requested_period(
        query_param_list: List[Dict[str, Union[str, int]]],
        url: str = TIDE_API_URL_DATA) -> gpd.GeoDataFrame:
    """
    Iterate over the list of API query parameters to fetch tide data for the requested period.

    Parameters
    ----------
    query_param_list : List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve tide data for the requested period.
    url : str = TIDE_API_URL_DATA
        Tide API HTTP request URL. Defaults to `TIDE_API_URL_DATA`.
        Can be either `TIDE_API_URL_DATA` or `TIDE_API_URL_DATA_CSV`.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched tide data for the requested period.

    Raises
    ------
    ValueError
        If an invalid URL is specified for the Tide API HTTP request.
    RuntimeError
        If failed to fetch tide data.
    """
    # Check if the provided URL is valid
    valid_urls = [TIDE_API_URL_DATA, TIDE_API_URL_DATA_CSV]
    if url not in valid_urls:
        raise ValueError(f"Invalid URL specified for the Tide API HTTP request. "
                         f"Valid URLs are: {', '.join(valid_urls)}")

    while True:
        try:
            tasks = []
            async with aiohttp.ClientSession() as session:
                # Create a list of tasks to fetch tide data for each query parameter
                for query_param in query_param_list:
                    tasks.append(fetch_tide_data(session, query_param=query_param, url=url))
                # Wait for all tasks to complete and retrieve the results
                query_results = await asyncio.gather(*tasks, return_exceptions=True)
                # Concatenate the results into a single GeoDataFrame and reset the index
                tide_data = gpd.GeoDataFrame(pd.concat(query_results)).reset_index(drop=True)
            return tide_data
        except TypeError:
            # If a TypeError occurs, it means the Tide API did not return the expected data format.
            # This can happen if the data source at the current URL is not available or the data is corrupt.
            # In such cases, try fetching the data from an alternative URL.
            if url == TIDE_API_URL_DATA:
                # Switch to the alternative URL
                url = TIDE_API_URL_DATA_CSV
            else:
                # If the alternative URL also fails, raise a RuntimeError to indicate the failure.
                raise RuntimeError("Failed to fetch tide data.")


def convert_to_nz_timezone(tide_data_utc: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Convert the time column in the initially retrieved tide data for the requested period from UTC to NZ timezone.

    Parameters
    ----------
    tide_data_utc : gpd.GeoDataFrame
        The original tide data obtained for the requested period with the time column expressed in UTC.

    Returns
    -------
    gpd.GeoDataFrame
        The tide data with the time column converted to NZ timezone.
    """
    # Create a copy of the tide data to avoid modifying the original DataFrame
    tide_data = tide_data_utc.copy()
    # Convert the 'time' column to datetime format
    tide_data['time'] = pd.to_datetime(tide_data['time'])
    # Convert the 'time' column to NZ timezone (Pacific/Auckland)
    tide_data['time'] = tide_data['time'].dt.tz_convert(tz='Pacific/Auckland')
    return tide_data


def fetch_tide_data_from_niwa(
        tide_query_loc: gpd.GeoDataFrame,
        datum: DatumType = DatumType.LAT,
        start_date: date = date.today(),
        total_days: int = 365,
        interval_mins: Optional[int] = None) -> gpd.GeoDataFrame:
    """
    Retrieve tide data from NIWA for the requested time period using the Tide API.

    Parameters
    ----------
    tide_query_loc : gpd.GeoDataFrame
        A GeoDataFrame containing the query coordinates and their positions.
    datum : DatumType = DatumType.LAT
        Datum used for fetching tide data from NIWA. Default value is LAT.
        Valid options are LAT for the Lowest Astronomical Tide and MSL for the Mean Sea Level.
    start_date : date = date.today()
        The start date for retrieving tide data. It can be in the past or present. Default is today's date.
    total_days : int = 365
        The total number of days of tide data to retrieve. Default is 365 days (one year).
    interval_mins : Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to retrieve only the highest and lowest tide data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched tide data from NIWA for the requested time period.
    """
    # Get the date ranges (i.e., start date and duration used for each API call)
    date_ranges = get_date_ranges(start_date, total_days)
    # Initialize an empty DataFrame to store the tide data in UTC
    tide_data_utc = pd.DataFrame()
    # Get the tide data for each of the tide query locations
    for _, row in tide_query_loc.iterrows():
        # Create a temporary GeoDataFrame containing a single query location
        query_loc_row = gpd.GeoDataFrame([row], crs=tide_query_loc.crs)
        # Get the latitude, longitude, and position of the query location
        lat, long, position = get_query_loc_coords_position(query_loc_row)
        # Generate a list of API query parameters used to retrieve tide data for the requested period
        query_param_list = gen_tide_query_param_list(lat, long, date_ranges, interval_mins, datum)
        # Iterate over the list of API query parameters to fetch tide data for the requested period
        query_loc_tide = asyncio.run(fetch_tide_data_for_requested_period(query_param_list))
        # Add the 'position' column to indicate the position of the query location
        query_loc_tide['position'] = position
        # Concatenate the tide data for the current query location with the overall tide data
        tide_data_utc = pd.concat([tide_data_utc, query_loc_tide])
    # Convert the time column from UTC to NZ timezone
    tide_data = convert_to_nz_timezone(tide_data_utc)
    # Filter out data beyond the requested time period and reset the index
    end_date = start_date + timedelta(days=total_days - 1)
    tide_data = tide_data.loc[tide_data['time'].dt.date <= end_date]
    tide_data = tide_data.reset_index(drop=True)
    # Rename columns to standardize column names
    new_col_names = {'time': 'datetime_nz', 'value': 'tide_metres'}
    tide_data.rename(columns=new_col_names, inplace=True)
    return tide_data


def get_highest_tide_datetime(tide_data: gpd.GeoDataFrame) -> pd.Timestamp:
    """
    Get the datetime of the most recent highest tide that occurred within the requested time period.

    Parameters
    ----------
    tide_data : gpd.GeoDataFrame
        The tide data fetched from NIWA for the requested time period.
        The time column is expressed in NZ timezone, which was converted from UTC.

    Returns
    -------
    pd.Timestamp
        The datetime of the most recent highest tide that occurred within the requested time period.
    """
    # Find the highest tide value
    max_tide_value = tide_data['tide_metres'].max()
    # Filter the tide data to include only the rows with the highest tide value
    highest_tide = tide_data[tide_data['tide_metres'] == max_tide_value]
    # Sort the filtered data by datetime in descending order to get the most recent highest tide
    highest_tide = highest_tide.sort_values(by=['datetime_nz'], ascending=False).reset_index(drop=True)
    # Get the datetime of the most recent highest tide
    highest_tide_datetime = highest_tide.iloc[0]['datetime_nz']
    return highest_tide_datetime


def get_highest_tide_datetime_span(
        highest_tide_datetime: pd.Timestamp,
        tide_length_mins: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Get the start and end datetimes of a tide event centered around the datetime of the highest tide.

    Parameters
    ----------
    highest_tide_datetime : pd.Timestamp
        The datetime of the most recent highest tide that occurred within the requested time period.
    tide_length_mins : int
        The length of the tide event in minutes.

    Returns
    -------
    Tuple[pd.Timestamp, pd.Timestamp]
        A tuple containing the start and end datetimes of the tide event centered around the
        datetime of the highest tide.
    """
    # Calculate half of the tide length in minutes
    half_tide_length_mins = tide_length_mins / 2
    # Convert half of the tide length to a timedelta object
    half_tide_length_timedelta = timedelta(minutes=half_tide_length_mins)
    # Calculate the start datetime by subtracting half of the tide length from the highest tide datetime
    start_datetime = highest_tide_datetime - half_tide_length_timedelta
    # Calculate the end datetime by adding half of the tide length to the highest tide datetime
    end_datetime = highest_tide_datetime + half_tide_length_timedelta
    # Adjust the end datetime to represent the precise end of the tide event by subtracting one second
    end_datetime -= timedelta(seconds=1)
    return start_datetime, end_datetime


def get_highest_tide_date_span(
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp) -> Tuple[date, int]:
    """
    Get the start date and duration in days of a tide event centered around the datetime of the highest tide.

    Parameters
    ----------
    start_datetime : pd.Timestamp
        The start datetime of the tide event centered around the datetime of the highest tide.
    end_datetime : pd.Timestamp
        The end datetime of the tide event centered around the datetime of the highest tide.

    Returns
    -------
    Tuple[date, int]
        A tuple containing the start date and the duration in days of a tide event centered around the
        datetime of the highest tide.
    """
    # Extract the start date from the start datetime
    start_date = start_datetime.date()
    # Extract the end date from the end datetime
    end_date = end_datetime.date()
    # Calculate the duration in days for the tide event
    total_days = (end_date - start_date).days + 1
    return start_date, total_days


def fetch_tide_data_around_highest_tide(
        tide_data: gpd.GeoDataFrame,
        tide_length_mins: int,
        interval_mins: int = 10,
        datum: DatumType = DatumType.LAT) -> gpd.GeoDataFrame:
    """
    Fetch tide data around the highest tide from NIWA for the specified tide length and interval.

    Parameters
    ----------
    tide_data : gpd.GeoDataFrame
        The tide data fetched from NIWA for the requested time period.
        The time column is expressed in NZ timezone, which was converted from UTC.
    tide_length_mins : int
        The length of the tide event in minutes.
    interval_mins : int = 10
        The time interval, in minutes, between each recorded tide data point. The default value is 10 minutes.
    datum : DatumType = DatumType.LAT
        Datum used for fetching tide data from NIWA. Default value is LAT.
        Valid options are LAT for the Lowest Astronomical Tide and MSL for the Mean Sea Level.

    Returns
    -------
    gpd.GeoDataFrame
        The tide data around the highest tide, fetched from NIWA, for the specified tide length and interval.
    """
    # Group the tide data by position and geometry
    grouped = tide_data.groupby(['position', tide_data['geometry'].to_wkt()])
    # Create an empty GeoDataFrame to store the tide data around the highest tide
    tide_data_around_highest_tide = gpd.GeoDataFrame()
    # Iterate over each group in the grouped data
    for _, group_data in grouped:
        # Get the datetime of the most recent highest tide that occurred within the requested time period
        # noinspection PyTypeChecker
        highest_tide_datetime = get_highest_tide_datetime(group_data)
        # Get the start and end datetimes of a tide event centered around the datetime of the highest tide
        start_datetime, end_datetime = get_highest_tide_datetime_span(highest_tide_datetime, tide_length_mins)
        # Get the start date and duration in days of a tide event centered around the datetime of the highest tide
        start_date, total_days = get_highest_tide_date_span(start_datetime, end_datetime)
        # Get the unique coordinates used to fetch tide data around the highest tide
        highest_tide_query_loc = group_data[['position', 'geometry']].drop_duplicates().reset_index(drop=True)
        # Fetch tide data around the highest tide from NIWA for the specified tide length and interval etc
        highest_tide_data = fetch_tide_data_from_niwa(
            highest_tide_query_loc, datum, start_date, total_days, interval_mins)
        # Filter the fetched tide data to include only the data within the tide event time range
        highest_tide_data = highest_tide_data.loc[
            highest_tide_data['datetime_nz'].between(start_datetime, end_datetime)].reset_index(drop=True)
        # Concatenate the filtered tide data to the existing data around the highest tide
        tide_data_around_highest_tide = pd.concat([tide_data_around_highest_tide, highest_tide_data])
    # Reset the index of the data around the highest tide
    tide_data_around_highest_tide = gpd.GeoDataFrame(tide_data_around_highest_tide).reset_index(drop=True)
    return tide_data_around_highest_tide


def get_time_mins_to_add(
        tide_data: pd.DataFrame,
        tide_length_mins: int,
        time_to_peak_mins: Union[int, float],
        interval_mins: int = 10) -> List[Union[float, int]]:
    """
    Get the time values in minutes to add to the tide data.

    Parameters
    ----------
    tide_data : pd.DataFrame
        The tide data for which time values in minutes will be calculated.
    tide_length_mins : int
        The length of the tide event in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when the tide is at its greatest (reaches maximum).
    interval_mins : int = 10
        The time interval, in minutes, between each recorded tide data point. The default value is 10 minutes.

    Returns
    -------
    List[Union[float, int]]
        A list containing the time values in minutes to add to the tide data.
    """
    # Get the number of rows in the tide data
    row_count = len(tide_data)
    # Calculate the time values in minutes based on the row count and the interval
    time_mins = np.arange(1, row_count + 1) * interval_mins
    # Adjust time values if the last value exceeds tide event duration
    if time_mins[-1] > tide_length_mins:
        # Remove the last time value and insert 0 at the beginning
        time_mins = np.insert(time_mins[:-1], 0, 0)
    # Calculate the middle index of the time values
    middle_index = ceil(len(time_mins) / 2) - 1
    # Get the time value corresponding to the middle index
    middle_point_mins = time_mins[middle_index]
    # Calculate the adjustment required to align time values with the peak tide time.
    adjustment = time_to_peak_mins - middle_point_mins
    # Add the adjustment to the time values
    time_mins = (time_mins + adjustment).tolist()
    return time_mins


def add_time_information(
        tide_data: gpd.GeoDataFrame,
        time_to_peak_mins: Union[int, float],
        interval_mins: int = 10,
        tide_length_mins: Optional[int] = None,
        total_days: Optional[int] = None,
        approach: ApproachType = ApproachType.KING_TIDE) -> gpd.GeoDataFrame:
    """
    Add time information (seconds, minutes, hours) to the tide data.

    Parameters
    ----------
    tide_data : gpd.GeoDataFrame
        The tide data for which time information will be added.
    time_to_peak_mins : Union[int, float]
        The time in minutes when the tide is at its greatest (reaches maximum).
    interval_mins : int = 10
        The time interval, in minutes, between each recorded tide data point. The default value is 10 minutes.
    tide_length_mins : Optional[int] = None
        The length of the tide event in minutes. Only required if the 'approach' is KING_TIDE.
    total_days : Optional[int] = None
        The total number of days for the tide event. Only required if the 'approach' is PERIOD_TIDE.
    approach : ApproachType = ApproachType.KING_TIDE
        The approach used to get the tide data. Default is KING_TIDE.

    Returns
    -------
    gpd.GeoDataFrame
        The tide data with added time information in seconds, minutes, and hours.

    Raises
    ------
    ValueError
        If 'time_to_peak_mins' is less than the minimum time to peak.

    Notes
    -----
        The minimum time to peak is calculated differently depending on the approach used:
        - For the KING_TIDE approach, it is half of the 'tide_length_mins'.
        - For the PERIOD_TIDE approach, it is half of the 'total_days' converted to minutes.
    """
    # If the approach is PERIOD_TIDE and total_days is provided but tide_length_mins is not,
    # calculate the tide length in minutes based on the total number of days
    if approach == ApproachType.PERIOD_TIDE and total_days is not None and tide_length_mins is None:
        # Convert total_days to minutes
        tide_length_mins = total_days * 24 * 60

    # Calculate the minimum time to peak based on half of the tide duration
    min_time_to_peak_mins = tide_length_mins / 2
    # Check if time_to_peak_mins is less than the minimum time to peak
    if time_to_peak_mins < min_time_to_peak_mins:
        if approach == ApproachType.KING_TIDE:
            # Error message for KING_TIDE approach
            message = f"If the 'approach' is KING_TIDE, 'time_to_peak_mins' must be at least half of " \
                      f"'tide_length_mins'. The current values are 'time_to_peak_mins': {time_to_peak_mins}, " \
                      f"'tide_length_mins': {tide_length_mins}."
            raise ValueError(message)
        else:
            # Error message for PERIOD_TIDE approach
            message = f"If the 'approach' is PERIOD_TIDE, 'time_to_peak_mins' must be at least half of " \
                      f"'total_days' in minutes. The current values are 'time_to_peak_mins': {time_to_peak_mins}, " \
                      f"'total_days': {total_days} (equivalent to {tide_length_mins} minutes)."
            raise ValueError(message)

    # Group the tide data by position and geometry
    grouped = tide_data.groupby(['position', tide_data['geometry'].to_wkt()])
    # Create a new GeoDataFrame to store tide data with time information
    tide_data_w_time = gpd.GeoDataFrame()
    # Iterate over each group in the grouped data
    for _, group_data in grouped:
        # Sort the group data by datetime
        group_data = group_data.sort_values(by='datetime_nz')
        # Get the time values in minutes to add to the tide data
        time_mins = get_time_mins_to_add(group_data, tide_length_mins, time_to_peak_mins, interval_mins)
        # Add the time information columns
        group_data['mins'] = time_mins
        group_data['hours'] = group_data['mins'] / 60
        group_data['seconds'] = group_data['mins'] * 60
        # Sort the group data by seconds
        group_data = group_data.sort_values(by="seconds").reset_index(drop=True)
        # Concatenate the group data to the main tide data with time information
        tide_data_w_time = pd.concat([tide_data_w_time, group_data])
    # Reset the index of the tide data with time information
    tide_data_w_time = gpd.GeoDataFrame(tide_data_w_time).reset_index(drop=True)
    return tide_data_w_time


def get_tide_data(
        tide_query_loc: gpd.GeoDataFrame,
        time_to_peak_mins: Union[int, float],
        approach: ApproachType = ApproachType.KING_TIDE,
        start_date: date = date.today(),
        total_days: Optional[int] = None,
        tide_length_mins: Optional[int] = None,
        interval_mins: int = 10,
        datum: DatumType = DatumType.LAT) -> gpd.GeoDataFrame:
    """
    Fetch tide data from NIWA using the Tide API based on the specified approach, datum, and other parameters.

    Parameters
    ----------
    tide_query_loc : gpd.GeoDataFrame
        A GeoDataFrame containing the query coordinates and their positions.
    time_to_peak_mins : Union[int, float]
        The time in minutes when the tide is at its greatest (reaches maximum).
    approach : ApproachType = ApproachType.KING_TIDE
        The approach used to get the tide data. Default is KING_TIDE.
    start_date : date = date.today()
        The start date for retrieving tide data. It can be in the past or present. Default is today's date.
    total_days : Optional[int] = None
        The total number of days for the tide event. Only required if the 'approach' is PERIOD_TIDE.
    tide_length_mins : Optional[int] = None
        The length of the tide event in minutes. Only required if the 'approach' is KING_TIDE.
    interval_mins : int = 10
        The time interval, in minutes, between each recorded tide data point. The default value is 10 minutes.
    datum : DatumType = DatumType.LAT
        Datum used for fetching tide data from NIWA. Default value is LAT.
        Valid options are LAT for the Lowest Astronomical Tide and MSL for the Mean Sea Level.

    Returns
    -------
    gpd.GeoDataFrame
        The tide data with added time information in seconds, minutes, and hours.

    Raises
    ------
    ValueError
        - If 'interval_mins' is None.
        - If the 'approach' is KING_TIDE and 'tide_length_mins' is None or 'total_days' is not None.
        - If the 'approach' is PERIOD_TIDE and 'total_days' is None or 'tide_length_mins' is not None.
    """
    log.info("Fetching 'tide' data from NIWA.")

    # Check if 'interval_mins' is None
    if interval_mins is None:
        raise ValueError("'interval_mins' must be provided, and it should not be None.")

    # Check if the selected approach is KING_TIDE or PERIOD_TIDE
    if approach == ApproachType.KING_TIDE:
        # If the approach is KING_TIDE: tide_length_mins is not provided or total_days is not None
        if tide_length_mins is None or total_days is not None:
            raise ValueError(
                "If the 'approach' is KING_TIDE, 'tide_length_mins' must be provided and "
                "'total_days' should not be provided (i.e. it should be None).")
        # Fetch the highest and lowest tide data from NIWA for a fixed number of days (365)
        tide_data = fetch_tide_data_from_niwa(
            tide_query_loc, datum, start_date, total_days=365, interval_mins=None)
        # Fetch tide data around the highest tide from NIWA for the specified tide length and interval
        tide_data_around_highest_tide = fetch_tide_data_around_highest_tide(
            tide_data, tide_length_mins, interval_mins, datum)
        # Add time information (seconds, minutes, hours) to the tide data
        tide_data_king = add_time_information(
            tide_data=tide_data_around_highest_tide,
            time_to_peak_mins=time_to_peak_mins,
            interval_mins=interval_mins,
            tide_length_mins=tide_length_mins,
            approach=approach)
        return tide_data_king
    else:
        # If the approach is PERIOD_TIDE: total_days is not provided or tide_length_mins is not None
        if total_days is None or tide_length_mins is not None:
            raise ValueError(
                "If the 'approach' is PERIOD_TIDE, 'total_days' must be provided and "
                "'tide_length_mins' should not be provided (i.e. it should be None).")
        # Fetch tide data from NIWA for the specified total days and interval
        tide_data = fetch_tide_data_from_niwa(tide_query_loc, datum, start_date, total_days, interval_mins)
        # Add time information (seconds, minutes, hours) to the tide data
        tide_data_period = add_time_information(
            tide_data=tide_data,
            time_to_peak_mins=time_to_peak_mins,
            interval_mins=interval_mins,
            total_days=total_days,
            approach=approach)
        return tide_data_period
