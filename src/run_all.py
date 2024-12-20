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
This script runs each module in the Digital Twin using a Sample Polygon.
"""

from enum import Enum
from types import ModuleType
from typing import Dict, Union

import geopandas as gpd

from src.digitaltwin import retrieve_static_boundaries
from src.digitaltwin.utils import LogLevel
from src.dynamic_boundary_conditions.rainfall import main_rainfall
from src.dynamic_boundary_conditions.rainfall.rainfall_enum import RainInputType, HyetoMethod
from src.dynamic_boundary_conditions.river import main_river
from src.dynamic_boundary_conditions.river.river_enum import BoundType
from src.dynamic_boundary_conditions.tide import main_tide_slr
from src.flood_model import bg_flood_model, process_hydro_dem


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        modules_to_parameters: Dict[ModuleType, Dict[str, Union[str, int, float, bool, None, Enum]]]) -> None:
    """
    Runs each module in the Digital Twin using the selected polygon and the defined parameters for each module's
    main function.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    modules_to_parameters : Dict[ModuleType, Dict[str, Union[str, int, float, bool, None, Enum]]]
        A dictionary that associates each module with the parameters necessary for its main function, including the
        option to set the log level for each module's root logger.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through the dictionary containing modules and their parameters
    for module, parameters in modules_to_parameters.items():
        # Call the main function of each module with the selected polygon and specified parameters
        module.main(selected_polygon_gdf, **parameters)


DEFAULT_MODULES_TO_PARAMETERS = {
    retrieve_static_boundaries: {
        "log_level": LogLevel.INFO
    },
    process_hydro_dem: {
        "log_level": LogLevel.INFO
    },
    main_rainfall: {
        "rcp": 2.6,
        "time_period": "2031-2050",
        "ari": 100,
        "storm_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "increment_mins": 10,
        "hyeto_method": HyetoMethod.ALT_BLOCK,
        "input_type": RainInputType.UNIFORM,
        "log_level": LogLevel.INFO
    },
    main_tide_slr: {
        "tide_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "interval_mins": 10,
        "proj_year": 2030,
        "confidence_level": "low",
        "ssp_scenario": "SSP1-2.6",
        "add_vlm": False,
        "percentile": 50,
        "log_level": LogLevel.INFO
    },
    main_river: {
        "flow_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "maf": True,
        "ari": None,
        "bound": BoundType.MIDDLE,
        "log_level": LogLevel.INFO
    },
    bg_flood_model: {
        "output_timestep": 1,
        "end_time": 2,
        "resolution": None,
        "mask": 9999,
        "gpu_device": -1,
        "small_nc": 0,
        "log_level": LogLevel.INFO
    }
}

if __name__ == '__main__':
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon, DEFAULT_MODULES_TO_PARAMETERS)
