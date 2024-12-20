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
This script provides utility functions for logging configuration and geospatial data manipulation.
"""

import inspect
import logging
import pathlib
import warnings
from enum import IntEnum

import geopandas as gpd
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)


class LogLevel(IntEnum):
    """
    Enum class representing different logging levels mapped to their corresponding numeric values from the
    logging library.

    Attributes
    ----------
    CRITICAL : int
        The critical logging level. Corresponds to logging.CRITICAL (50).
    ERROR : int
        The error logging level. Corresponds to logging.ERROR (40).
    WARNING : int
        The warning logging level. Corresponds to logging.WARNING (30).
    INFO : int
        The info logging level. Corresponds to logging.INFO (20).
    DEBUG : int
        The debug logging level. Corresponds to logging.DEBUG (10).
    NOTSET : int
        The not-set logging level. Corresponds to logging.NOTSET (0).
    """
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    NOTSET = logging.NOTSET


def log_execution_info() -> None:
    """
    Logs a debug message indicating the execution of the function in the script.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Obtain the stack frame of the calling function (two frames up in the call stack)
    stack_frame = inspect.currentframe().f_back.f_back
    # Extract the name of the script file (without the path) where the function is being executed
    script_name = pathlib.Path(stack_frame.f_globals["__file__"]).name
    # Extract the name of the function currently being executed
    function_name = stack_frame.f_code.co_name
    # Log a debug message indicating the execution of the function in the script
    log.debug(f"Executing {function_name}() in {script_name}")


def setup_logging(log_level: LogLevel = LogLevel.INFO) -> None:
    """
    Configures the root logger with the specified log level and formats, captures warnings, and excludes specific
    loggers from propagating their messages to the root logger. Additionally, logs a debug message indicating the
    execution of the function in the script.

    Parameters
    ----------
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
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
    # Define the logging format and date format
    logging_format = "%(asctime)s | %(levelname)-8s | %(name)-30s %(lineno)4d | %(funcName)-50s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    # Create and configure the root logger with the specified log level and formats
    logging.basicConfig(level=log_level, format=logging_format, datefmt=date_format)
    # Enable capturing Python warnings and redirect them to the logging system
    logging.captureWarnings(True)
    # Suppress (ignore) Python warnings from appearing in the console
    warnings.simplefilter("ignore")
    # List of loggers to prevent messages from reaching the root logger
    loggers_to_exclude = [
        "urllib3",
        "fiona",
        "botocore",
        "pyproj",
        "asyncio",
        "rasterio",
        "scrapy",
        "distributed",
        "selenium",
        "s3transfer"
    ]
    # Iterate through the loggers to exclude
    for logger_name in loggers_to_exclude:
        # Get the logger instance for each name in the list
        logger = logging.getLogger(logger_name)
        # Disable log message propagation from these loggers to the root logger
        logger.propagate = False
    # Log the execution of the function in the script
    log_execution_info()


def get_catchment_area(catchment_area: gpd.GeoDataFrame, to_crs: int = 2193) -> gpd.GeoDataFrame:
    """
    Convert the coordinate reference system (CRS) of the catchment area GeoDataFrame to the specified CRS.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    to_crs : int = 2193
        Coordinate Reference System (CRS) code to convert the catchment area to. Default is 2193.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area with the transformed CRS.
    """
    return catchment_area.to_crs(to_crs)


def get_nz_boundary(engine: Engine, to_crs: int = 2193) -> gpd.GeoDataFrame:
    """
    Get the boundary of New Zealand in the specified Coordinate Reference System (CRS).

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    to_crs : int = 2193
        Coordinate Reference System (CRS) code to which the boundary will be converted. Default is 2193.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame representing the boundary of New Zealand in the specified CRS.
    """
    # Query the 'region_geometry' table from the database using the provided engine
    query = "SELECT * FROM region_geometry;"
    region_geometry = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Dissolve and explode the geometries to get the boundary of New Zealand
    nz_boundary = region_geometry.dissolve(aggfunc="sum").explode(index_parts=True).reset_index(level=0, drop=True)
    # Calculate the area of each geometry and sort them in descending order
    nz_boundary["geometry_area"] = nz_boundary["geometry"].area
    nz_boundary = nz_boundary.sort_values(by="geometry_area", ascending=False).head(1)
    # Convert to the desired coordinate reference system (CRS)
    nz_boundary = nz_boundary.to_crs(to_crs)
    return nz_boundary
