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
Generates the requested water level uniform boundary model input for BG-Flood.
"""

import logging
import pathlib

import pandas as pd

from src.dynamic_boundary_conditions.tide import main_tide_slr

log = logging.getLogger(__name__)


def generate_uniform_boundary_input(bg_flood_dir: pathlib.Path, tide_slr_data: pd.DataFrame) -> None:
    """
    Generates the requested water level uniform boundary model input for BG-Flood.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory.
    tide_slr_data : pd.DataFrame
        A DataFrame containing the combined tide and sea level rise data.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Remove any existing uniform boundary input files in the BG-Flood directory
    main_tide_slr.remove_existing_boundary_inputs(bg_flood_dir)
    # Log that the generation of uniform boundary model inputs has started
    log.info("Generating the uniform boundary model inputs for BG-Flood.")
    # Group the combined tide and sea level rise data by position
    grouped = tide_slr_data.groupby('position')
    # Iterate over each group and generate the required uniform boundary input file
    for position, group_data in grouped:
        # Extract the necessary columns from the group data
        input_data = group_data[['seconds', 'tide_slr_metres']]
        # Define the file path for the uniform boundary input file based on the position
        file_path = bg_flood_dir / f"{position}_bnd.txt"
        # Save the input data as a tab-separated text file at the specified file path
        input_data.to_csv(file_path, sep='\t', index=False, header=False)
        # Add the "# Water level boundary" line at the beginning of the uniform boundary input file
        with open(file_path, 'r+') as file:
            content = file.read()
            file.seek(0, 0)
            file.write('# Water level boundary\n' + content)
    # Log a message indicating the successful generation of the uniform boundary model inputs
    log.info("Successfully generated the uniform boundary model inputs for BG-Flood.")
