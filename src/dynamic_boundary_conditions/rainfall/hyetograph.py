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
Get hyetograph data and generate interactive hyetograph plots for sites located within the catchment area.
"""

from typing import Union
from math import floor, ceil

import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import plotly.express as px

from src.dynamic_boundary_conditions.rainfall.rainfall_enum import HyetoMethod


def get_transposed_data(rain_depth_in_catchment: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and transpose the retrieved scenario data from the database for sites within the catchment area and
    return it in transposed Pandas DataFrame format.

    Parameters
    ----------
    rain_depth_in_catchment : pd.DataFrame
        Rainfall depths for sites within the catchment area for a specified scenario retrieved from the database.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the cleaned and transposed scenario data.
    """
    # Drop unnecessary columns
    catchment_data = rain_depth_in_catchment.drop(columns=["category", "rcp", "time_period", "ari", "aep"])
    # Convert duration column names from text to duration columns in minutes
    for index, column_name in enumerate(catchment_data.columns):
        # Convert duration column names in minutes (text) to duration columns in minutes (integer)
        if column_name.endswith("m"):
            catchment_data.columns.values[index] = int(column_name[:-1])
        # Convert duration column names in hours (text) to duration columns in minutes (integer)
        elif column_name.endswith("h"):
            catchment_data.columns.values[index] = int(column_name[:-1]) * 60
    # Transpose the DataFrame
    transposed_catchment_data = (
        catchment_data.set_index("site_id").rename_axis("").transpose().rename_axis("duration_mins").reset_index()
    )
    return transposed_catchment_data


def get_interpolated_data(
        transposed_catchment_data: pd.DataFrame,
        increment_mins: int,
        interp_method: str) -> pd.DataFrame:
    """
    Perform temporal interpolation on the transposed scenario data to the desired time interval
    for sites within the catchment area.

    Parameters
    ----------
    transposed_catchment_data : pd.DataFrame
        Transposed scenario data retrieved from the database.
    increment_mins : int
        Time interval in minutes.
    interp_method : str
        Temporal interpolation method to be used. Refer to 'scipy.interpolate.interp1d()' for available methods.
        One of 'linear', 'nearest', 'nearest-up', 'zero', 'slinear', 'quadratic', 'cubic', 'previous', or 'next'.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the scenario data interpolated at the desired time interval for sites within the
        catchment area.

    Raises
    ------
    ValueError
        - If the specified 'increment_mins' is out of range.
        - If the specified 'interp_method' is not supported.
    """
    # Extract the duration column from the transposed catchment data
    duration = transposed_catchment_data['duration_mins']
    # Check if increment_mins is within the valid range
    if increment_mins < duration.iloc[0] or increment_mins > duration.iloc[-1]:
        raise ValueError(f"Increment minute {increment_mins} is out of range, "
                         f"needs to be between {duration.iloc[0]} and {duration.iloc[-1]}.")
    # Create a new array of duration minutes to interpolate the data for
    duration_new = np.arange(increment_mins, duration.iloc[-1] + increment_mins, increment_mins)
    # Drop the last element of 'duration_new' if it is bigger than the last element of the original 'duration'
    # because it would throw a ValueError as it is above the interpolation range's maximum value
    duration_new = duration_new[:-1] if duration_new[-1] > duration.iloc[-1] else duration_new
    # Create a DataFrame to hold the interpolated data with 'duration_mins' as the first column
    interp_catchment_data = pd.DataFrame(duration_new, columns=["duration_mins"])
    # Perform interpolation for each site in the transposed catchment data
    for column_num in range(1, len(transposed_catchment_data.columns)):
        # Get the depth values for the current site
        depth = transposed_catchment_data.iloc[:, column_num]
        try:
            # Create an interpolation function using the duration and depth values
            f_func = interp1d(duration, depth, kind=interp_method)
        except NotImplementedError as e:
            # Raise an error if the specified interpolation method is not supported
            raise ValueError(f"Invalid interpolation method: '{interp_method}'. "
                             f"Refer to 'scipy.interpolate.interp1d()' for available methods.") from e
        # Get the site ID associated with the current depth values
        site_id = depth.name
        # Interpolate the depth values for the new duration range
        depth_new = pd.Series(f_func(duration_new), name=site_id)
        # Concatenate the interpolated depth values with the duration column in the interpolated catchment data
        interp_catchment_data = pd.concat([interp_catchment_data, depth_new], axis=1)
    return interp_catchment_data


def get_interp_incremental_data(interp_catchment_data: pd.DataFrame) -> pd.DataFrame:
    """
    Get the incremental rainfall depths (difference between current and preceding cumulative rainfall)
    for sites within the catchment area and return it in Pandas DataFrame format.

    Parameters
    ----------
    interp_catchment_data : pd.DataFrame
        Interpolated scenario data for sites within the catchment area.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the incremental rainfall depths.
    """
    # Calculate the difference between consecutive rows to get the incremental rainfall depths
    interp_increment_data = interp_catchment_data.diff()[1:]
    # Include the first row of interpolated data as the initial cumulative rainfall values
    interp_increment_data = pd.concat([interp_catchment_data.head(1), interp_increment_data])
    # Remove the 'duration_mins' column from the DataFrame
    interp_increment_data.drop("duration_mins", axis=1, inplace=True)
    # Concatenate the 'duration_mins' column with the incremental data to include it in the resulting DataFrame
    interp_increment_data = pd.concat(
        [interp_catchment_data["duration_mins"], interp_increment_data], axis=1)
    return interp_increment_data


def get_storm_length_increment_data(interp_increment_data: pd.DataFrame, storm_length_mins: int) -> pd.DataFrame:
    """
    Get the incremental rainfall depths for sites within the catchment area for a specific storm duration.

    Parameters
    ----------
    interp_increment_data : pd.DataFrame
        Incremental rainfall depths for sites within the catchment area.
    storm_length_mins : int
        Storm duration in minutes.

    Returns
    -------
    pd.DataFrame
        Incremental rainfall depths for sites within the catchment area for the specified storm duration.

    Raises
    ------
    ValueError
        If the specified 'storm_length_mins' is less than the minimum storm duration available in the data.
    """
    # Determine the minimum storm duration available in the data
    min_storm_length_mins = interp_increment_data["duration_mins"].iloc[0]
    # Check if the specified storm duration is valid
    if storm_length_mins < min_storm_length_mins:
        raise ValueError(f"Storm duration (storm_length_mins) needs to be at least '{int(min_storm_length_mins)}'.")
    # Filter the data to include only rows within the specified storm duration
    storm_length_filter = (interp_increment_data["duration_mins"] <= storm_length_mins)
    storm_length_data = interp_increment_data[storm_length_filter]
    return storm_length_data


def add_time_information(
        site_data: pd.DataFrame,
        storm_length_mins: int,
        time_to_peak_mins: Union[int, float],
        increment_mins: int,
        hyeto_method: HyetoMethod) -> pd.DataFrame:
    """
    Add time information (seconds, minutes, and hours column) to the hyetograph data based on the
    selected hyetograph method.

    Parameters
    ----------
    site_data : pd.DataFrame
        Hyetograph data for a rainfall site or gauge.
    storm_length_mins : int
        Storm duration in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    hyeto_method : HyetoMethod
        Hyetograph method to be used.

    Returns
    -------
    pd.DataFrame
        Hyetograph data with added time information.

    Raises
    ------
    ValueError
        If the specified 'time_to_peak_mins' is less than half of the storm duration.
    """
    # Determine the minimum time to peak based on the storm duration
    min_time_to_peak_mins = storm_length_mins / 2
    # Check if the specified time to peak is valid
    if time_to_peak_mins < min_time_to_peak_mins:
        raise ValueError(
            "'time_to_peak_mins' (time in minutes when rainfall is at its greatest) needs to be "
            "at least half of 'storm_length_mins' (storm duration).")

    if hyeto_method == HyetoMethod.ALT_BLOCK:
        # Alternating Block Method: Place the maximum incremental rainfall depth at the peak position (center),
        # arrange the remaining incremental rainfall depths alternatively in descending order after and before
        # the peak.
        row_count = len(site_data)
        # Calculate minutes from the peak for all incremental rainfall depth data
        mins_from_peak_right = np.arange(1, ceil((row_count + 1) / 2)) * increment_mins
        if (row_count % 2) == 0:
            mins_from_peak_left = np.arange(0, floor((row_count + 1) / 2)) * -increment_mins
            mins_from_peak = [mins for sublist in zip(mins_from_peak_left, mins_from_peak_right) for mins in sublist]
        else:
            mins_from_peak_left = np.arange(1, floor((row_count + 1) / 2)) * -increment_mins
            mins_from_peak = [mins for sublist in zip(mins_from_peak_right, mins_from_peak_left) for mins in sublist]
            mins_from_peak.insert(0, 0)
        # Add time (minutes) information using minutes from the peak to allocate incremental rainfall depths
        site_data = site_data.assign(mins=time_to_peak_mins + np.array(mins_from_peak))
    else:
        # Chicago Method: Place the initial incremental rainfall depth at the peak position and split it in half
        # (left and right), further split the next incremental rainfall depths in half and arrange them before and after
        # (left and right) of the previous split incremental rainfall depths.

        # Add time (minutes) information to allocate the split incremental rainfall depths
        mins_start = time_to_peak_mins - site_data["duration_mins"][0] + increment_mins / 2
        mins_end = time_to_peak_mins + site_data["duration_mins"][0] + increment_mins / 2
        mins = np.arange(mins_start, mins_end, increment_mins / 2)
        site_data = site_data.assign(mins=mins)
    # Add extra time information, i.e., hours and seconds columns
    site_data = site_data.assign(hours=site_data["mins"] / 60,
                                 seconds=site_data["mins"] * 60)
    # Sort the data based on the seconds column in ascending order
    site_data = site_data.sort_values(by="seconds", ascending=True)
    # Drop the duration_mins column as it is no longer needed and reset the index
    site_data = site_data.drop(columns=["duration_mins"]).reset_index(drop=True)
    return site_data


def transform_data_for_selected_method(
        interp_increment_data: pd.DataFrame,
        storm_length_mins: int,
        time_to_peak_mins: Union[int, float],
        increment_mins: int,
        hyeto_method: HyetoMethod) -> pd.DataFrame:
    """
    Transform the storm length incremental rainfall depths for sites within the catchment area based on
    the selected hyetograph method and return hyetograph depths data for all sites within the catchment area
    in Pandas DataFrame format.

    Parameters
    ----------
    interp_increment_data : pd.DataFrame
        Incremental rainfall depths for sites within the catchment area.
    storm_length_mins : int
        Storm duration in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    hyeto_method : HyetoMethod
        Hyetograph method to be used.

    Returns
    -------
    pd.DataFrame
        Hyetograph depths data for all sites within the catchment area.
    """
    # Get the incremental rainfall depths data within the specified storm duration
    storm_length_data = get_storm_length_increment_data(interp_increment_data, storm_length_mins)
    # Initialize a list to hold the hyetograph data
    hyetograph_sites_data = []
    # Iterate over each site in the storm length data
    for column_num in range(1, len(storm_length_data.columns)):
        # Extract the duration and depth data for the current site
        site_data = storm_length_data.iloc[:, [0, column_num]]
        # Apply the selected hyetograph method to transform the data
        if hyeto_method == HyetoMethod.ALT_BLOCK:
            # Alternating Block Method: Place the maximum incremental rainfall depth at the peak position (center),
            # arrange the remaining incremental rainfall depths alternatively in descending order after and before
            # the peak.
            site_data = site_data.sort_values(by=site_data.columns[1], ascending=False)
        else:
            # Chicago Method: Place the initial incremental rainfall depth at the peak position and split it in half
            # (left and right), further split the next incremental rainfall depths in half and arrange them before and
            # after (left and right) of the previous split incremental rainfall depths.
            site_data_right = site_data.div(2)
            site_data_left = site_data_right[::-1]
            site_data = pd.concat([site_data_left, site_data_right]).reset_index(drop=True)
        # Add time information to the transformed site_data
        site_data = add_time_information(site_data, storm_length_mins, time_to_peak_mins, increment_mins, hyeto_method)
        # Append the transformed site_data to the list
        hyetograph_sites_data.append(site_data)
    # Concatenate the transformed site data into a single DataFrame
    hyetograph_depth = pd.concat(hyetograph_sites_data, axis=1, ignore_index=False)
    # Remove any duplicated columns in the DataFrame
    hyetograph_depth = hyetograph_depth.loc[:, ~hyetograph_depth.columns.duplicated(keep="last")]
    return hyetograph_depth


def hyetograph_depth_to_intensity(
        hyetograph_depth: pd.DataFrame,
        increment_mins: int,
        hyeto_method: HyetoMethod) -> pd.DataFrame:
    """
    Convert hyetograph depths data to hyetograph intensities data for all sites within the catchment area.

    Parameters
    ----------
    hyetograph_depth: pd.DataFrame
        Hyetograph depths data for sites within the catchment area.
    increment_mins : int
        Time interval in minutes.
    hyeto_method : HyetoMethod
        Hyetograph method to be used.

    Returns
    -------
    pd.DataFrame
        Hyetograph intensities data for all sites within the catchment area.
    """
    # Determine the duration interval based on the hyetograph method
    duration_interval = increment_mins if hyeto_method == HyetoMethod.ALT_BLOCK else (increment_mins / 2)
    # Extract the depths data for all sites
    sites_depth = hyetograph_depth.drop(columns=["mins", "hours", "seconds"])
    # Convert the depths to intensities by dividing by the duration interval and multiplying by 60
    sites_intensity = sites_depth / duration_interval * 60
    # Extract the time columns from the original hyetograph depths data
    sites_time = hyetograph_depth[["mins", "hours", "seconds"]]
    # Concatenate the intensities and time columns into a single DataFrame
    hyetograph_intensity = pd.concat([sites_intensity, sites_time], axis=1)
    return hyetograph_intensity


def get_hyetograph_data(
        rain_depth_in_catchment: pd.DataFrame,
        storm_length_mins: int,
        time_to_peak_mins: Union[int, float],
        increment_mins: int,
        interp_method: str,
        hyeto_method: HyetoMethod) -> pd.DataFrame:
    """
    Get hyetograph intensities data for all sites within the catchment area and return it in Pandas DataFrame format.

    Parameters
    ----------
    rain_depth_in_catchment : pd.DataFrame
        Rainfall depths for sites within the catchment area for a specified scenario retrieved from the database.
    storm_length_mins : int
        Storm duration in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    interp_method : str
        Temporal interpolation method to be used. Refer to 'scipy.interpolate.interp1d()' for available methods.
        One of 'linear', 'nearest', 'nearest-up', 'zero', 'slinear', 'quadratic', 'cubic', 'previous', or 'next'.
    hyeto_method : HyetoMethod
        Hyetograph method to be used.

    Returns
    -------
    pd.DataFrame
        Hyetograph intensities data for all sites within the catchment area.
    """
    # Clean and transpose the rainfall depths data
    transposed_catchment_data = get_transposed_data(rain_depth_in_catchment)
    # Interpolate the rainfall depths data to the desired time interval
    interp_catchment_data = get_interpolated_data(transposed_catchment_data, increment_mins, interp_method)
    # Compute the incremental rainfall depths for the catchment area
    interp_increment_data = get_interp_incremental_data(interp_catchment_data)
    # Transform the storm length incremental rainfall depths for sites within the catchment area
    # using the selected hyetograph method
    hyetograph_depth = transform_data_for_selected_method(
        interp_increment_data, storm_length_mins, time_to_peak_mins, increment_mins, hyeto_method)
    # Convert the hyetograph depths data to hyetograph intensities data
    hyetograph_data = hyetograph_depth_to_intensity(hyetograph_depth, increment_mins, hyeto_method)
    return hyetograph_data


def hyetograph_data_wide_to_long(hyetograph_data: pd.DataFrame) -> pd.DataFrame:
    """
    Transform hyetograph intensities data for all sites within the catchment area from wide format to long format.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.

    Returns
    -------
    pd.DataFrame
        Hyetograph intensities data in long format.
    """
    # Initialize an empty DataFrame to store the long-format hyetograph data
    hyetograph_data_long = pd.DataFrame()
    # Iterate over each row in the wide-format hyetograph data.
    for _, row in hyetograph_data.iterrows():
        # Create a time slice with rain intensity measurements.
        hyeto_time_slice = row[:-3].to_frame("rain_intensity_mmhr").rename_axis("site_id").reset_index()
        # Add time information to the time slice.
        hyeto_time_slice = hyeto_time_slice.assign(mins=row["mins"], hours=row["hours"], seconds=row["seconds"])
        # Concatenate the time slice to the long-format hyetograph data.
        hyetograph_data_long = pd.concat([hyetograph_data_long, hyeto_time_slice])
    return hyetograph_data_long


def hyetograph(hyetograph_data: pd.DataFrame, ari: float) -> None:
    """
    Create interactive individual hyetograph plots for sites within the catchment area.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    ari : float
        Average Recurrence Interval (ARI) value. Valid options are 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.

    Returns
    -------
    None
        This function does not return any value.
    """
    for site_id in hyetograph_data.columns.values[:-3]:
        # Retrieve the hyetograph data for the current site, including time and rain intensity measurements.
        hyeto_site_data = hyetograph_data[[f"{site_id}", "mins", "hours", "seconds"]]
        # Rename the column
        hyeto_site_data.columns.values[0] = "rain_intensity_mmhr"
        # Create a bar chart using Plotly
        hyeto_fig = px.bar(
            hyeto_site_data,
            title=f"{ari}-year storm: site {site_id}",
            x="mins",
            y="rain_intensity_mmhr",
            labels={"mins": "Time (Minutes)",
                    "rain_intensity_mmhr": "Rainfall Intensity (mm/hr)"}
        )
        # Customize the layout of the hyetograph figure.
        hyeto_fig.update_layout(
            title_font_size=20,
            title_x=0.5,
            bargap=0,
            updatemenus=[
                dict(
                    type="dropdown",
                    direction="down",
                    x=0.99,
                    y=0.99,
                    buttons=list([
                        dict(
                            args=["type", "bar"],
                            label="Bar Chart",
                            method="restyle"
                        ),
                        dict(
                            args=["type", "line"],
                            label="Line Chart",
                            method="restyle"
                        )
                    ]),
                )
            ]
        )
        # Display the hyetograph figure.
        hyeto_fig.show()
