# -*- coding: utf-8 -*-
"""
Generates combined tide and sea level rise (SLR) data for a specific projection year, taking into account the provided
confidence level, SSP scenario, inclusion of Vertical Land Motion (VLM), percentile, and more.
"""  # noqa: D400

import logging
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely.wkt
from scipy.interpolate import interp1d

log = logging.getLogger(__name__)


def get_slr_scenario_data(
        slr_data: gpd.GeoDataFrame,
        confidence_level: str,
        ssp_scenario: str,
        add_vlm: bool,
        percentile: int) -> gpd.GeoDataFrame:
    """
    Get sea level rise scenario data based on the specified confidence_level, ssp_scenario, add_vlm, and percentile.

    Parameters
    ----------
    slr_data : gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise data.
    confidence_level : str
        The desired confidence level for the scenario data. Valid values are 'low' or 'medium'.
    ssp_scenario : str
        The desired Shared Socioeconomic Pathways (SSP) scenario for the scenario data.
        Valid options for both low and medium confidence are: 'SSP1-2.6', 'SSP2-4.5', or 'SSP5-8.5'.
        Additional options for medium confidence are: 'SSP1-1.9' or 'SSP3-7.0'.
    add_vlm : bool
        Indicates whether to include Vertical Land Motion (VLM) in the scenario data.
        Set to True if VLM should be included, False otherwise.
    percentile : int
        The desired percentile for the scenario data. Valid values are 17, 50, or 83.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise scenario data based on the specified
        confidence_level, ssp_scenario, add_vlm, and percentile.

    Raises
    ------
    ValueError
        - If an invalid 'confidence_level' value is provided.
        - If an invalid 'ssp_scenario' value is provided.
        - If an invalid 'add_vlm' value is provided.
        - If an invalid 'percentile' value is provided.
    """
    log.info("Extracting the requested 'sea_level_rise' scenario data.")

    # Merge ssp and scenario into one column
    slr_data['ssp_scenario'] = slr_data['ssp'].astype(str) + '-' + slr_data['scenario'].astype(str)
    # Remove 'ssp' and 'scenario' column
    slr_data = slr_data.drop(columns=['ssp', 'scenario'])

    # Check if the provided confidence level is valid
    valid_conf_level = slr_data['confidence_level'].unique().tolist()
    if confidence_level not in valid_conf_level:
        raise ValueError(f"Invalid value '{confidence_level}' for confidence_level. Must be one of {valid_conf_level}.")
    # Filter the sea level rise data based on the desired confidence level
    slr_scenario = slr_data[slr_data["confidence_level"] == confidence_level]

    # Check if the provided SSP scenario is valid
    valid_ssp_scenario = slr_scenario['ssp_scenario'].unique().tolist()
    if ssp_scenario not in valid_ssp_scenario:
        raise ValueError(f"Invalid value '{ssp_scenario}' for ssp_scenario. Must be one of {valid_ssp_scenario}.")
    # Filter the sea level rise scenario data based on the desired SSP scenario
    slr_scenario = slr_scenario[slr_scenario['ssp_scenario'] == ssp_scenario]

    # Check if the provided add_vlm value is valid
    valid_add_vlm = slr_scenario['add_vlm'].unique().tolist()
    if add_vlm not in valid_add_vlm:
        raise ValueError(f"Invalid value '{add_vlm}' for add_vlm. Must be one of {valid_add_vlm}.")
    # Filter the sea level rise scenario data based on the inclusion of Vertical Land Motion (VLM)
    slr_scenario = slr_scenario[slr_scenario['add_vlm'] == add_vlm]

    # Get the percentiles from the column names and check if the provided percentile value is valid
    percentile_cols = [col for col in slr_data.columns if re.match(r'^p\d+', col)]
    valid_percentile = [int(col[1:]) for col in percentile_cols]
    if percentile not in valid_percentile:
        raise ValueError(f"Invalid value '{percentile}' for percentile. Must be one of {valid_percentile}.")
    # Select specific columns from the sea level rise scenario data including the desired percentile
    slr_scenario = slr_scenario[['siteid', 'year', f"p{percentile}", 'geometry', 'position']]

    # Rename the percentile column to 'slr_metres' and reset the index
    slr_scenario_data = slr_scenario.rename(columns={f"p{percentile}": "slr_metres"}).reset_index(drop=True)
    return slr_scenario_data


def get_interpolated_slr_scenario_data(
        slr_scenario_data: gpd.GeoDataFrame,
        increment_year: int = 1,
        interp_method: str = "linear") -> gpd.GeoDataFrame:
    """
    Interpolates sea level rise scenario data based on the specified year interval and interpolation method.

    Parameters
    ----------
    slr_scenario_data : gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise scenario data.
    increment_year : int = 1
        The year interval used for interpolation. Defaults to 1 year.
    interp_method : str = "linear"
        Temporal interpolation method to be used. Defaults to 'linear'.
        Available methods: 'linear', 'nearest', 'nearest-up', 'zero', 'slinear', 'quadratic', 'cubic', 'previous',
        'next'. Refer to 'scipy.interpolate.interp1d()' for more details.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the interpolated sea level rise scenario data.

    Raises
    ------
    ValueError
        - If the specified 'increment_year' is out of range.
        - If the specified 'interp_method' is not supported.
    """
    # Group the sea level rise scenario data by site, geometry, and position
    grouped = slr_scenario_data.groupby(['siteid', slr_scenario_data['geometry'].to_wkt(), 'position'])
    # Create an empty GeoDataFrame to store the interpolated scenario data
    slr_interp_scenario = gpd.GeoDataFrame()
    # Iterate over each group and perform interpolation
    for group_name, group_data in grouped:
        # Extract the year values and sea level rise values for the current group
        group_year, slr_metres = group_data['year'], group_data['slr_metres']
        # Check if increment_year is within the valid range
        valid_increment_year = group_year.iloc[-1] - group_year.iloc[0]
        if increment_year <= 0 or increment_year > valid_increment_year:
            raise ValueError(f"Increment year {increment_year} is out of range, "
                             f"needs to be between 1 and {valid_increment_year}.")
        # Create a new array of years to interpolate the data for
        group_year_new = np.arange(group_year.iloc[0], group_year.iloc[-1] + increment_year, increment_year)
        # Drop the last element of 'group_year_new' if it is bigger than the last element of the original 'group_year'
        # because it would throw a ValueError as it is above the interpolation range's maximum value
        group_year_new = group_year_new[:-1] if group_year_new[-1] > group_year.iloc[-1] else group_year_new
        # Create a DataFrame to hold the interpolated group data with 'year' as the first column
        interp_group_data = pd.DataFrame(group_year_new, columns=["year"])
        try:
            # Create an interpolation function using the group_years and sea level rise values
            f_func = interp1d(group_year, slr_metres, kind=interp_method)
        except NotImplementedError as e:
            # Raise an error if the specified interpolation method is not supported
            raise ValueError(f"Invalid interpolation method: '{interp_method}'. "
                             f"Refer to 'scipy.interpolate.interp1d()' for available methods.") from e
        # Interpolate the sea level rise values for the new year range
        group_data_new = pd.Series(f_func(group_year_new), name='slr_metres')
        # Concatenate the interpolated sea level rise values with the year column in the interp_group_data
        interp_group_data = pd.concat([interp_group_data, group_data_new], axis=1)
        # Assign the site ID, geometry, and position to the interpolated group data
        site_id, geometry, position = group_name
        interp_group_data[['siteid', 'geometry', 'position']] = site_id, shapely.wkt.loads(geometry), position
        # Create a GeoDataFrame with the interpolated group data and set the coordinate reference system
        interp_group_data = gpd.GeoDataFrame(interp_group_data, crs=group_data.crs)
        # Concatenate the interpolated group data to the overall interpolated scenario data
        slr_interp_scenario = pd.concat([slr_interp_scenario, interp_group_data])
    # Reset the index of the interpolated sea level rise scenario data
    slr_interp_scenario = gpd.GeoDataFrame(slr_interp_scenario).reset_index(drop=True)
    return slr_interp_scenario


def add_slr_to_tide(
        tide_data: gpd.GeoDataFrame,
        slr_interp_scenario: gpd.GeoDataFrame,
        proj_year: int) -> pd.DataFrame:
    """
    Add sea level rise (SLR) data to the tide data for a specific projection year and
    return the combined tide and sea level rise value.

    Parameters
    ----------
    tide_data : gpd.GeoDataFrame
        A GeoDataFrame containing tide data with added time information (seconds, minutes, hours) and location details.
    slr_interp_scenario : gpd.GeoDataFrame
        A GeoDataFrame containing the interpolated sea level rise scenario data.
    proj_year : int
        The projection year for which sea level rise data should be added to the tide data.

    Returns
    -------
    pd.DataFrame
        A DataFrame that contains the combined tide and sea level rise data for the specified projection year.

    Raises
    ------
    ValueError
        If an invalid 'proj_year' value is provided.
    """  # noqa: D400
    log.info("Adding 'sea_level_rise' data to 'tide' data for the requested scenario.")

    # Make a copy of the tide_data DataFrame to avoid modifying the original data
    tide_df = tide_data.copy()
    # Extract the year from the 'datetime_nz' column
    tide_df['year'] = tide_df['datetime_nz'].dt.year

    # Get the minimum year from the tide data
    minimum_current_year = tide_df['year'].min()
    # Filter the sea level rise data to include only years greater than or equal to the minimum year
    slr_interp_scenario = slr_interp_scenario[slr_interp_scenario['year'] >= minimum_current_year]
    # Reset the index after filtering
    slr_interp_scenario = slr_interp_scenario.reset_index(drop=True)
    # Check if the provided projection year is valid
    valid_proj_year = slr_interp_scenario['year'].unique().tolist()
    if proj_year not in valid_proj_year:
        raise ValueError(f"Invalid value '{proj_year}' for proj_year. Must be one of {valid_proj_year}.")

    # Select only the necessary columns for further processing
    tide_df = tide_df[['year', 'seconds', 'tide_metres', 'position', 'geometry']]
    # Group the tide data by year, position, and geometry
    grouped = tide_df.groupby(['year', 'position', tide_df['geometry'].to_wkt()])
    # Create an empty DataFrame to store the tide data with added sea level rise data
    tide_slr_data = gpd.GeoDataFrame()
    # Iterate over each group and add sea level rise to the tide data
    for group_name, group_data in grouped:
        # Extract the current year and position from the group_name
        current_year, position, _ = group_name
        # Create a filter to select rows in the slr_interp_scenario DataFrame with matching current year and position
        current_filt = (slr_interp_scenario['year'] == current_year) & (slr_interp_scenario['position'] == position)
        # Create a filter to select rows in the slr_interp_scenario DataFrame with matching projection year and position
        proj_filt = (slr_interp_scenario['year'] == proj_year) & (slr_interp_scenario['position'] == position)
        # Retrieve the sea level rise value for the current year
        current_slr_metres = slr_interp_scenario[current_filt]['slr_metres'].iloc[0]
        # Retrieve the sea level rise value for the projection year
        proj_slr_metres = slr_interp_scenario[proj_filt]['slr_metres'].iloc[0]
        # Calculate the sea level rise difference between the projection year and current year
        group_data['slr_metres'] = proj_slr_metres - current_slr_metres
        # Concatenate the current group data with the tide_slr_data DataFrame
        tide_slr_data = pd.concat([tide_slr_data, group_data])
    # Calculate the combined tide and sea level rise values
    tide_slr_data['tide_slr_metres'] = tide_slr_data['tide_metres'] + tide_slr_data['slr_metres']
    # Select the necessary columns from the tide_slr_data DataFrame
    tide_slr_data = tide_slr_data[['seconds', 'tide_slr_metres', 'position']]
    # Reset the index of the tide_slr_data DataFrame
    tide_slr_data = tide_slr_data.reset_index(drop=True)
    return tide_slr_data


def get_combined_tide_slr_data(
        tide_data: gpd.GeoDataFrame,
        slr_data: gpd.GeoDataFrame,
        proj_year: int,
        confidence_level: str,
        ssp_scenario: str,
        add_vlm: bool,
        percentile: int,
        increment_year: int = 1,
        interp_method: str = "linear") -> pd.DataFrame:
    """
    Generate the combined tide and sea level rise (SLR) data for a specific projection year, considering the given
    confidence_level, ssp_scenario, add_vlm, percentile, and more.

    Parameters
    ----------
    tide_data : gpd.GeoDataFrame
        A GeoDataFrame containing tide data with added time information (seconds, minutes, hours) and location details.
    slr_data : gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise data.
    proj_year : int
        The projection year for which the combined tide and sea level rise data should be generated.
    confidence_level : str
        The desired confidence level for the sea level rise data.
    ssp_scenario : str
        The desired Shared Socioeconomic Pathways (SSP) scenario for the sea level rise data.
    add_vlm : bool
        Indicates whether Vertical Land Motion (VLM) should be included in the sea level rise data.
    percentile : int
        The desired percentile for the sea level rise data.
    increment_year : int = 1
        The year interval used for interpolating the sea level rise data. Defaults to 1 year.
    interp_method : str = "linear"
        Temporal interpolation method used for interpolating the sea level rise data. Defaults to 'linear'.
        Available methods: 'linear', 'nearest', 'nearest-up', 'zero', 'slinear', 'quadratic', 'cubic', 'previous',
        'next'. Refer to 'scipy.interpolate.interp1d()' for more details.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the combined tide and sea level rise data for the specified projection year,
        taking into account the provided confidence_level, ssp_scenario, add_vlm, percentile, and more.
    """  # noqa: D400
    # Get sea level rise scenario data based on the specified confidence_level, ssp_scenario, add_vlm, and percentile
    slr_scenario_data = get_slr_scenario_data(slr_data, confidence_level, ssp_scenario, add_vlm, percentile)
    # Interpolate sea level rise scenario data based on the specified year interval and interpolation method
    slr_interp_scenario = get_interpolated_slr_scenario_data(slr_scenario_data, increment_year, interp_method)
    # Add sea level rise data to the tide data for a specific projection year
    tide_slr_data = add_slr_to_tide(tide_data, slr_interp_scenario, proj_year)
    return tide_slr_data
