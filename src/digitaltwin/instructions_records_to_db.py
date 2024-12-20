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
This script processes 'static_boundary_instructions' records, validates URLs and instruction fields, and stores them in
the 'geospatial_layers' table of the database.
"""

import json
import logging
import pathlib
from typing import Dict, Union

import requests
import pandas as pd
import validators
from sqlalchemy.engine import Engine

from src.digitaltwin.tables import GeospatialLayers, create_table

log = logging.getLogger(__name__)


def validate_url_reachability(section: str, url: str) -> None:
    """
    Validate the URL by checking its format and reachability.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    url : str
        The URL to validate.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    ValueError
        - If the URL is invalid.
        - If the URL is unreachable.
    """
    # Check if the URL is valid
    if not validators.url(url):
        raise ValueError(f"Invalid URL provided for {section}: '{url}'")
    # Check if the URL is reachable
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        # Raise an exception if the response status code indicates an error
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Unreachable URL provided for {section}: '{url}'\n{e}")


def validate_instruction_fields(section: str, instruction: Dict[str, Union[str, int]]) -> None:
    """
    Validate the fields of an instruction.
    Each instruction should provide either 'coverage_area' or 'unique_column_name', but not both.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    instruction : Dict[str, Union[str, int]]
        The instruction details.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    ValueError
        - If both 'coverage_area' and 'unique_column_name' are provided.
        - If both 'coverage_area' and 'unique_column_name' are not provided.
    """
    # Retrieve the values of 'coverage_area' and 'unique_column_name' from the instruction dictionary
    coverage_area = instruction.get("coverage_area")
    unique_column_name = instruction.get("unique_column_name")
    # Check if both 'coverage_area' and 'unique_column_name' are provided
    if coverage_area and unique_column_name:
        raise ValueError(
            f"Both 'coverage_area' and 'unique_column_name' provided for {section}. Only one should be provided.")
    # Check if both 'coverage_area' and 'unique_column_name' are not provided
    if not coverage_area and not unique_column_name:
        raise ValueError(
            f"Neither 'coverage_area' nor 'unique_column_name' provided for {section}. One must be provided.")


def read_and_check_instructions_file() -> pd.DataFrame:
    """
    Read and check the static_boundary_instructions file, validating URLs and instruction fields.

    Returns
    -------
    pd.DataFrame
        The processed instructions DataFrame.
    """
    # Path to the 'static_boundary_instructions.json' file
    instruction_file = pathlib.Path("src/digitaltwin/static_boundary_instructions.json")
    # Read the 'static_boundary_instructions.json' file
    with open(instruction_file, "r") as file:
        # Load content from the file
        instructions = json.load(file)
        # Iterate through each section
        for section, instruction in instructions.items():
            # Validate the URL and its reachability
            validate_url_reachability(section, instruction.get("url"))
            # Validate the instruction fields
            validate_instruction_fields(section, instruction)
        # Create the DataFrame from the instructions dictionary
        instructions_df = pd.DataFrame(instructions).transpose().reset_index(names='section')
        # Strip leading and trailing whitespace from the URLs
        instructions_df['url'] = instructions_df['url'].str.strip()
        # Drop duplicated records in case they exist in the 'static_boundary_instructions' file
        instructions_df = instructions_df.drop_duplicates(subset=instructions_df.columns.difference(['section']))
    return instructions_df


def get_existing_geospatial_layers(engine: Engine) -> pd.DataFrame:
    """
    Retrieve existing geospatial layers from the 'geospatial_layers' table.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the existing geospatial layers.
    """
    # SQL query to retrieve specific columns from the geospatial_layers table
    existing_layer_query = f"""
    SELECT data_provider, layer_id
    FROM {GeospatialLayers.__tablename__};
    """
    # Execute the query and read the results into a DataFrame
    existing_layers_df = pd.read_sql(existing_layer_query, engine)
    return existing_layers_df


def get_non_existing_records(instructions_df: pd.DataFrame, existing_layers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get 'static_boundary_instructions' records that are not available in the database.

    Parameters
    ----------
    instructions_df : pd.DataFrame
        Data frame containing the 'static_boundary_instructions' records.
    existing_layers_df : pd.DataFrame
        Data frame containing the existing 'static_boundary_instructions' records from the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the 'static_boundary_instructions' records that are not available in the database.
    """
    # Merge the instructions DataFrame with the existing data DataFrame
    merged_df = instructions_df.merge(existing_layers_df, on=['data_provider', 'layer_id'], how='left', indicator=True)
    # Filter for records that only exist in the instructions DataFrame (non-existing records)
    non_existing_records = merged_df[merged_df['_merge'] == 'left_only'].drop(columns='_merge')
    # Drop the 'section' column and move the 'url' column to the end
    non_existing_records = non_existing_records.drop(columns=["section"])
    non_existing_records['url'] = non_existing_records.pop('url')
    return non_existing_records


def store_instructions_records_to_db(engine: Engine) -> None:
    """
    Store 'static_boundary_instructions' records in the 'geospatial_layers' table in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Create the 'geospatial_layers' table if it doesn't exist
    create_table(engine, GeospatialLayers)
    # Retrieve existing layers from the 'geospatial_layers' table
    existing_layers_df = get_existing_geospatial_layers(engine)
    # Read and check the instructions file
    instructions_df = read_and_check_instructions_file()
    # Get 'static_boundary_instructions' records that are not available in the database.
    non_existing_records = get_non_existing_records(instructions_df, existing_layers_df)

    if non_existing_records.empty:
        log.info("No new 'static_boundary_instructions' records found. All records already exist in the database.")
    else:
        # Store the non-existing records to the 'geospatial_layers' table
        log.info("Adding new 'static_boundary_instructions' records to the database.")
        non_existing_records.to_sql(GeospatialLayers.__tablename__, engine, index=False, if_exists="append")
