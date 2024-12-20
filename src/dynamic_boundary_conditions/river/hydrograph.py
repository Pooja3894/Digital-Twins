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
This script handles the task of obtaining REC river inflow scenario data, whether it's Mean Annual Flood (MAF) or
Average Recurrence Interval (ARI)-based, and generates corresponding hydrograph data for the requested scenarios.
"""

import logging
from typing import List, Union, Optional
import re

import geopandas as gpd

from src.dynamic_boundary_conditions.river.river_enum import BoundType

log = logging.getLogger(__name__)


def clean_rec_inflow_data(rec_inflows_w_input_points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Selects and renames specific columns that represent REC river inflow data from the input GeoDataFrame.

    Parameters
    ----------
    rec_inflows_w_input_points : gpd.GeoDataFrame
        A GeoDataFrame containing data for REC river inflow segments whose boundary points align with the
        boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold,
        along with their corresponding river input points used in the BG-Flood model.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame with selected and renamed columns representing REC river inflow data.
    """
    # Copy input GeoDataFrame to preserve original data
    rec_inflow_data = rec_inflows_w_input_points.copy()
    # Select columns starting with 'h' and include 'areakm2', 'river_input_point' and 'dem_resolution'
    rec_inflow_data = rec_inflow_data.filter(regex=r'^h|^areakm2$|^river_input_point|^dem_resolution$')
    # Define a mapping of old column names to new column names for renaming
    column_mapping = {
        r'^h_c18_': 'flow_',
        r'^hcse_': 'flow_se_',
        r'_yr$|y$': '',
    }
    # Rename columns using the column_mapping dictionary and regex matching
    rec_inflow_data.columns = rec_inflow_data.columns.to_series().replace(column_mapping, regex=True)
    # Move the 'areakm2' column to the last column
    rec_inflow_data['areakm2'] = rec_inflow_data.pop('areakm2')
    return rec_inflow_data


def extract_valid_ari_values(rec_inflow_data: gpd.GeoDataFrame) -> List[int]:
    """
    Extracts valid ARI (Annual Recurrence Interval) values from the column names of the REC river inflow data.

    Parameters
    ----------
    rec_inflow_data : gpd.GeoDataFrame
        A GeoDataFrame containing REC river inflow data with column names that include ARI values.

    Returns
    -------
    List[int]
        A list of valid ARI values extracted from the column names of the REC river inflow data.
    """
    # Define the regex pattern to extract ARI values from column names
    ari_pattern = re.compile(r"flow_(\d+)")
    # Get the column names of the river flow data
    column_names = rec_inflow_data.columns
    # Extract valid ARI values from column names using the regex pattern
    valid_ari_values = [int(match.group(1)) for col_name in column_names if (match := ari_pattern.search(col_name))]
    # Sort and return the list of valid ARI values
    return sorted(valid_ari_values)


def get_rec_inflow_scenario_data(
        rec_inflows_w_input_points: gpd.GeoDataFrame,
        maf: bool = True,
        ari: Optional[int] = None,
        bound: BoundType = BoundType.MIDDLE) -> gpd.GeoDataFrame:
    """
    Obtain the requested REC river inflow scenario data, which can be either Mean Annual Flood (MAF)-based or
    Average Recurrence Interval (ARI)-based scenario data.

    Parameters
    ----------
    rec_inflows_w_input_points : gpd.GeoDataFrame
        A GeoDataFrame containing data for REC river inflow segments whose boundary points align with the
        boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold,
        along with their corresponding river input points used in the BG-Flood model.
    maf : bool = True
        Set to True to obtain MAF-based scenario data or False to obtain ARI-based scenario data.
    ari : Optional[int] = None
        The Average Recurrence Interval (ARI) value. Valid options are 5, 10, 20, 50, 100, or 1000.
        Mandatory when 'maf' is set to False, and should be set to None when 'maf' is set to True.
    bound : BoundType = BoundType.MIDDLE
        Set the type of bound (estimate) for the REC river inflow scenario data.
        Valid options include: 'BoundType.LOWER', 'BoundType.MIDDLE', or 'BoundType.UPPER'.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the requested REC river inflow scenario data.

    Raises
    ------
    ValueError
        - If 'ari' is provided when 'maf' is set to True (i.e. 'maf' is True and 'ari' is not set to None).
        - If 'ari' is not provided when 'maf' is set to False (i.e. 'maf' is False and 'ari' is set to None).
        - If an invalid 'ari' value is provided.
    """
    # Selects and renames specific columns that represent REC river inflow data
    rec_inflow_data = clean_rec_inflow_data(rec_inflows_w_input_points)

    log.info("Extracting the requested REC river inflow scenario data.")
    if maf:
        # If MAF-based scenario is selected, ensure 'ari' is not provided (set to None)
        if ari is not None:
            raise ValueError("When 'maf' is set to True, 'ari' should be set to None (i.e. should not be provided).")
        # Extract MAF-based scenario and select specific columns of interest
        sel_columns = ["river_input_point", "dem_resolution", "areakm2", "flow_maf", "flow_se_maf"]
        scenario_data = rec_inflow_data[sel_columns]
        scenario_data["middle"] = scenario_data["flow_maf"]
        # Rename columns in the extracted data for clarity
        scenario_data = scenario_data.rename(
            columns={
                "flow_maf": "maf",
                "flow_se_maf": "flow_se"
            })
    else:
        # If ARI-based scenario is selected, ensure 'ari' is provided (not set to None)
        if ari is None:
            raise ValueError("When 'maf' is set to False, 'ari' should not be set to None (i.e. should be provided).")
        # Check for valid ARI values
        valid_ari_values = extract_valid_ari_values(rec_inflow_data)
        if ari not in valid_ari_values:
            raise ValueError(f"Invalid 'ari' value: {ari}. Must be one of {valid_ari_values}.")
        # Extract ARI-based scenario and select specific columns of interest
        sel_columns = ["river_input_point", "dem_resolution", "areakm2", "flow_maf", f"flow_se_{ari}", f"flow_{ari}"]
        scenario_data = rec_inflow_data[sel_columns]
        # Rename columns in the extracted data for clarity
        scenario_data = scenario_data.rename(
            columns={
                "flow_maf": "maf",
                f"flow_se_{ari}": "flow_se",
                f"flow_{ari}": "middle"
            })
    # Calculate lower and upper bounds for the scenario based on 'middle' values and 'flow_se'
    scenario_data["lower"] = scenario_data["middle"] - scenario_data["flow_se"]
    scenario_data["upper"] = scenario_data["middle"] + scenario_data["flow_se"]
    # Remove unnecessary column and reset the index
    scenario_data = scenario_data.drop(columns=["flow_se"]).reset_index(drop=True)
    # Assign a unique identifier (river_input_point_no) to each 'river_input_point,' starting from 1
    scenario_data.insert(0, "river_input_point_no", scenario_data.index + 1)
    # Select specific columns to retain only the relevant information for the scenario
    sel_columns = ["river_input_point_no", "river_input_point", "dem_resolution", "areakm2", "maf", f"{bound.value}"]
    rec_inflow_scenario_data = scenario_data[sel_columns]
    return rec_inflow_scenario_data


def get_hydrograph_data(
        rec_inflows_w_input_points: gpd.GeoDataFrame,
        flow_length_mins: int,
        time_to_peak_mins: Union[int, float],
        maf: bool = True,
        ari: Optional[int] = None,
        bound: BoundType = BoundType.MIDDLE) -> gpd.GeoDataFrame:
    """
    Generate hydrograph data for the requested REC river inflow scenario.

    Parameters
    ----------
    rec_inflows_w_input_points : gpd.GeoDataFrame
        A GeoDataFrame containing data for REC river inflow segments whose boundary points align with the
        boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold,
        along with their corresponding river input points used in the BG-Flood model.
    flow_length_mins : int
        Duration of the river flow in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when flow is at its greatest (reaches maximum).
    maf : bool = True
        Set to True to obtain MAF-based scenario data or False to obtain ARI-based scenario data.
    ari : Optional[int] = None
        The Average Recurrence Interval (ARI) value. Valid options are 5, 10, 20, 50, 100, or 1000.
        Mandatory when 'maf' is set to False, and should be set to None when 'maf' is set to True.
    bound : BoundType = BoundType.MIDDLE
        Set the type of bound (estimate) for the REC river inflow scenario data.
        Valid options include: 'BoundType.LOWER', 'BoundType.MIDDLE', or 'BoundType.UPPER'.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing hydrograph data for the requested REC river inflow scenario.

    Raises
    ------
    ValueError
        If the specified 'time_to_peak_mins' is less than half of the river flow duration.
    """
    # Determine the minimum time to peak based on the river flow duration
    min_time_to_peak_mins = flow_length_mins / 2
    # Check if the specified time to peak is valid
    if time_to_peak_mins < min_time_to_peak_mins:
        raise ValueError("'time_to_peak_mins' needs to be at least half of 'flow_length_mins' (river flow duration).")
    #  Obtain the requested REC river inflow scenario data
    rec_inflow_scenario_data = get_rec_inflow_scenario_data(rec_inflows_w_input_points, maf, ari, bound)
    # Initialize an empty data dictionary to store hydrograph data
    hydro_data_dict = dict(
        river_input_point_no=[],
        river_input_point=[],
        dem_resolution=[],
        areakm2=[],
        mins=[],
        flow=[]
    )
    # Generate hydrograph data for the requested REC river inflow scenario
    for _, row in rec_inflow_scenario_data.iterrows():
        hydro_data_dict["river_input_point_no"].extend([row["river_input_point_no"]] * 3)
        hydro_data_dict["river_input_point"].extend([row["river_input_point"]] * 3)
        hydro_data_dict["dem_resolution"].extend([row["dem_resolution"]] * 3)
        hydro_data_dict["areakm2"].extend([row["areakm2"]] * 3)
        # Generate three different time steps: before peak, at peak, and after peak
        hydro_data_dict["mins"].extend([
            time_to_peak_mins - min_time_to_peak_mins,
            time_to_peak_mins,
            time_to_peak_mins + min_time_to_peak_mins
        ])
        # Calculate flow values for the hydrograph
        hydro_data_dict["flow"].extend([row["maf"] * 0.1, row["middle"], 0])
    # Create a GeoDataFrame with the hydrograph data dictionary
    hydrograph_data = gpd.GeoDataFrame(hydro_data_dict, geometry="river_input_point", crs=rec_inflow_scenario_data.crs)
    # Add extra time information columns: hours and seconds
    hydrograph_data["hours"] = hydrograph_data["mins"] / 60
    hydrograph_data["seconds"] = hydrograph_data["mins"] * 60
    # Move the 'flow' column to the last column
    hydrograph_data["flow"] = hydrograph_data.pop("flow")
    return hydrograph_data
