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
This script handles the processing of input files for the BG-Flood Model, executes the flood model, stores the
resulting model output metadata in the database, and incorporates the model output into GeoServer for visualization.
"""

import logging
import os
import pathlib
import platform
import subprocess
from datetime import datetime
from typing import Tuple, Union, Optional, TextIO

import geopandas as gpd
import xarray as xr
from newzealidar.utils import get_dem_by_geometry
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.tables import BGFloodModelOutput, create_table, check_table_exists
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.flood_model.flooded_buildings import find_flooded_buildings
from src.flood_model.flooded_buildings import store_flooded_buildings_in_database
from src.flood_model.serve_model import add_model_output_to_geoserver

log = logging.getLogger(__name__)

Base = declarative_base()


def get_valid_bg_flood_dir() -> pathlib.Path:
    """
    Get the valid BG-Flood Model directory.

    Returns
    -------
    pathlib.Path
        The valid BG-Flood Model directory.

    Raises
    ------
    FileNotFoundError
        If the BG-Flood Model directory is not found or is not a valid directory.
    """
    # Get the BG-Flood Model directory from the environment variable
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    # Check if the directory exists and is a valid directory
    if bg_flood_dir.exists() and bg_flood_dir.is_dir():
        return bg_flood_dir
    # If the directory doesn't exist or is not a valid directory, raise a FileNotFoundError
    raise FileNotFoundError(f"BG-Flood Model not found at: '{bg_flood_dir}'")


def get_new_model_output_path() -> pathlib.Path:
    """
    Get a new file path for saving the BG Flood model output with the current timestamp included in the filename.

    Returns
    -------
    pathlib.Path
        The path to the BG Flood model output file.
    """
    # Get the BG Flood model output directory from the environment variable
    model_output_dir = config.get_env_variable("DATA_DIR_MODEL_OUTPUT", cast_to=pathlib.Path)
    # Create the BG Flood model output directory if it does not already exist
    model_output_dir.mkdir(parents=True, exist_ok=True)
    # Get the current timestamp in "YYYY_MM_DD_HH_MM_SS" format
    dt_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    # Create the BG Flood model output path with the current timestamp
    model_output_path = (model_output_dir / f"output_{dt_string}.nc")
    return model_output_path


def get_model_output_metadata(
        model_output_path: pathlib.Path,
        catchment_area: gpd.GeoDataFrame) -> Tuple[str, str, str]:
    """
    Get metadata related to the BG Flood model output.

    Parameters
    ----------
    model_output_path : pathlib.Path
        The path to the BG Flood model output file.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    Tuple[str, str, str]
        A tuple containing three elements: the name of the BG Flood model output file, its absolute path as a string,
        and the Well-Known Text (WKT) representation of the catchment area's geometry.
    """
    # Get the name of the BG Flood model output file
    output_name = model_output_path.name
    # Get the absolute path of the BG Flood model output file as a string
    output_path = model_output_path.as_posix()
    # Get the WKT representation of the catchment area's geometry
    catchment_geom = catchment_area["geometry"].to_wkt().iloc[0]
    # Return the metadata as a tuple
    return output_name, output_path, catchment_geom


def store_model_output_metadata_to_db(
        engine: Engine,
        model_output_path: pathlib.Path,
        catchment_area: gpd.GeoDataFrame) -> int:
    """
    Store metadata related to the BG Flood model output in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    model_output_path : pathlib.Path
        The path to the BG Flood model output file.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    int
        Returns the model id of the new flood_model produced
    """
    # Create the 'bg_flood_model_output' table in the database if it doesn't exist
    create_table(engine, BGFloodModelOutput)
    # Get the metadata related to the BG Flood model output
    output_name, output_path, geometry = get_model_output_metadata(model_output_path, catchment_area)
    # Create a new query object representing the BG-Flood model output metadata
    query = insert(BGFloodModelOutput).values(file_name=output_name, file_path=output_path, geometry=geometry)
    # Execute the query to store the BG Flood model output metadata in the database while retrieving id
    with engine.begin() as conn:
        result = conn.execute(query)
    model_id = result.inserted_primary_key[0]
    # Log a message indicating the successful storage of BG-Flood model output metadata in the database
    log.info("BG-Flood model output metadata successfully stored in the database.")
    return model_id


def model_output_from_db_by_id(engine: Engine, model_id: int) -> pathlib.Path:
    """
    Retrieves the path to the model output file from the database by model_id

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    model_id: int
        The ID of the flood model output being queried for

    Returns
    -------
    pathlib.Path
        The path to the model output file
    """
    # Execute a query to get the model output record based on the 'flood_model_id' column
    query = text("SELECT * FROM bg_flood_model_output WHERE unique_id=:flood_model_id").bindparams(
        flood_model_id=model_id)
    # Check table exists before querying
    bg_flood_table = "bg_flood_model_output"
    if not check_table_exists(engine, bg_flood_table):
        raise FileNotFoundError(f"{bg_flood_table} table does not exist")
    row = engine.execute(query).fetchone()
    # If the row is empty then we could not find the model output
    if row is None:
        raise FileNotFoundError(f"bg_flood_model_output table does not contain row with unique_id: {model_id}")
    # Extract the file path from the retrieved record
    latest_output_path = pathlib.Path(row["file_path"])
    # Extract the file path from the retrieved record
    return latest_output_path


def model_extents_from_db_by_id(engine: Engine, model_id: int) -> gpd.GeoDataFrame:
    """
    Finds the extents of a model output in gpd.GeoDataFrame format

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    model_id: int
        The ID of the flood model output being queried for

    Returns
    -------
    gpd.GeoDataFrame
        Returns the geometry (extents) of the flood model output.
    """
    # Execute a query to get the model output record based on the 'flood_model_id' column
    bg_flood_table = "bg_flood_model_output"
    if not check_table_exists(engine, bg_flood_table):
        raise FileNotFoundError(f"{bg_flood_table} table does not exist")
    query = text("SELECT geometry FROM bg_flood_model_output WHERE unique_id=:flood_model_id").bindparams(
        flood_model_id=model_id)
    geometry = gpd.read_postgis(query, engine, geom_col='geometry')
    if len(geometry) == 0:
        raise FileNotFoundError(f"{bg_flood_table} table does not have any rows with unique_id = {model_id}")
    return geometry


def add_crs_to_model_output(engine: Engine, flood_model_output_id: int) -> None:
    """
    Add Coordinate Reference System (CRS) to the BG-Flood model output.

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    flood_model_output_id: int
        The ID of the flood model output being queried for


    Returns
    -------
    None
        This function does not return any value.
    """
    # Get the path to the latest BG-Flood model output file from the database
    model_output_file = model_output_from_db_by_id(engine, flood_model_output_id)
    # Create a temporary file path for saving modifications before replacing the current latest model output file
    temp_file = model_output_file.with_name(f"{model_output_file.stem}_temp{model_output_file.suffix}")

    # Open the latest model output file as a xarray dataset
    with xr.open_dataset(model_output_file, decode_coords="all") as latest_output:
        # Check if the dataset lacks a Coordinate Reference System (CRS)
        if latest_output.rio.crs is None:
            # Add the Coordinate Reference System (CRS) information to the dataset
            latest_output.rio.write_crs("epsg:2193", inplace=True)
            # Set the spatial dimensions explicitly for proper interpretation
            latest_output.rio.set_spatial_dims(x_dim="xx_P0", y_dim="yy_P0", inplace=True)
            # Reproject the dataset to the specified CRS
            latest_output = latest_output.rio.reproject("epsg:2193")
            # Save the modified dataset to the temporary file
            latest_output.to_netcdf(temp_file)

    # Check if both the original and temporary files exist
    if model_output_file.exists() and temp_file.exists():
        # Replace the original file with the modified temporary file
        temp_file.replace(model_output_file)
    log.debug(f"Added CRS info to {model_output_file}")


def process_rain_input_files(bg_flood_dir: pathlib.Path, param_file: TextIO) -> None:
    """
    Process rain input files and write their parameter values to the BG-Flood parameter file.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory containing the rain input files.
    param_file : TextIO
        The file object representing the parameter file where the parameter values will be written.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Loop through the rain input files in the BG-Flood directory
    for rain_input_file_path in bg_flood_dir.glob('rain_forcing.*'):
        # Extract the file extension from the rain input file
        file_extension = rain_input_file_path.suffix[1:]
        # Get the name of the rain input file
        rain_file = rain_input_file_path.name
        # Check if the file extension is 'txt'
        if file_extension == "txt":
            # Write the plain text rain parameter line to the BG-Flood parameter file
            param_file.write(f"rain = {rain_file};\n")
        else:
            # If the input file is in netCDF format, read it using xarray and get the name of the rain variable
            with xr.open_dataset(rain_input_file_path) as input_file:
                rain_var_name = list(input_file.data_vars)[0]
            # Write the netCDF rain parameter line to the BG-Flood parameter file
            param_file.write(f"rain = {rain_file}?{rain_var_name};\n")


def process_boundary_input_files(bg_flood_dir: pathlib.Path, param_file: TextIO) -> None:
    """
    Process uniform boundary input files and write their parameter values to the BG-Flood parameter file.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory containing the uniform boundary input files.
    param_file : TextIO
        The file object representing the parameter file where the parameter values will be written.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Loop through the boundary input files in the BG-Flood directory
    for boundary_input_file_path in bg_flood_dir.glob('*_bnd.txt'):
        # Extract the boundary position from the file name
        boundary_position = boundary_input_file_path.stem.split('_')[0]
        # Get the name of the boundary input file
        boundary_file = boundary_input_file_path.name
        # Write the boundary parameter line to the BG-Flood parameter file
        param_file.write(f"{boundary_position} = {boundary_file},2;\n")


def process_river_input_files(bg_flood_dir: pathlib.Path, param_file: TextIO) -> None:
    """
    Process river input files, rename them, and write their parameter values to the BG-Flood parameter file.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory containing the river input files.
    param_file : TextIO
        The file object representing the parameter file where the parameter values will be written.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Loop through the river input files in the BG-Flood directory
    for river_input_file_path in bg_flood_dir.glob('river[0-9]*_*.txt'):
        # Split the file name into parts based on underscores
        file_name_parts = river_input_file_path.stem.split('_')
        # Create the new file name by combining the first part and the file extension
        new_river_file = file_name_parts[0] + river_input_file_path.suffix
        # Create the new file path with the new name
        new_file_path = river_input_file_path.with_name(new_river_file)
        # Rename the input file with the new name
        river_input_file_path.rename(new_file_path)
        # Join the remaining parts of the file name with commas to form the extents parameter value
        extents = ','.join(file_name_parts[1:])
        # Write the river parameter line to the BG-Flood parameter file
        param_file.write(f"river = {new_river_file},{extents};\n")


def prepare_bg_flood_model_inputs(
        bg_flood_dir: pathlib.Path,
        model_output_path: pathlib.Path,
        hydro_dem_path: pathlib.Path,
        resolution: Union[int, float],
        output_timestep: Union[int, float],
        end_time: Union[int, float],
        mask: Union[int, float] = 9999,
        gpu_device: int = 0,
        small_nc: int = 0) -> None:
    """
    Prepare inputs for the BG-Flood Model.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood Model directory.
    model_output_path : pathlib.Path
        The new file path for saving the BG Flood model output with the current timestamp included in the filename.
    hydro_dem_path : pathlib.Path,
        The file path of the Hydrologically conditioned DEM (Hydro DEM) for the specified catchment area.
    resolution : Union[int, float]
        The grid resolution in meters for metric grids, representing the size of each grid cell.
    output_timestep : Union[int, float]
        Time step between model outputs in seconds. If the value is set to 0 then no output is generated.
    end_time : Union[int, float]
        Time in seconds when the model stops. If the value is set to 0 then the model initializes but does not run.
    mask : Union[int, float] = 9999
        The mask value is used to remove blocks from computation where the topography elevation (zb) is greater than
        the specified value. Default value is 9999.0 (no areas are masked).
    gpu_device : int = 0
        Specify the GPU device to be used. Default value is 0 (the first available GPU).
        Set the value to -1 to use the CPU. For other GPUs, use values 2 and above.
    small_nc : int = 0
        Specify whether the output should be saved as short integers to reduce the size of the output file.
        Set the value to 1 to enable short integer conversion, or set it to 0 to save all variables as floats.
        Default value is 0.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Read the Hydro DEM file using xarray and get the name of the elevation variable
    with xr.open_dataset(hydro_dem_path) as dem_file:
        elev_var_name = list(dem_file.data_vars)[1]

    # Construct the file path for the BG-Flood Model parameter file
    bg_param_file_path = bg_flood_dir / "BG_param.txt"

    # Open the BG-Flood Model parameter file for writing
    with open(bg_param_file_path, "w+") as param_file:
        # Write general parameter values to the parameter file
        param_file.write(f"topo = {hydro_dem_path.as_posix()}?{elev_var_name};\n"
                         f"dx = {resolution};\n"
                         f"outputtimestep = {output_timestep};\n"
                         f"endtime = {end_time};\n"
                         f"mask = {mask};\n"
                         f"gpudevice = {gpu_device};\n"
                         f"smallnc = {small_nc};\n"
                         f"outfile = {model_output_path.as_posix()};\n"
                         f"outvars = h, hmax, zb, zs, u, v;\n")

        # Process rain input files and write their parameter values to the parameter file
        process_rain_input_files(bg_flood_dir, param_file)
        # Process uniform boundary input files and write their parameter values to the parameter file
        process_boundary_input_files(bg_flood_dir, param_file)
        # Process river input files, rename them, and write their parameter values to the parameter file
        process_river_input_files(bg_flood_dir, param_file)


def run_bg_flood_model(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        model_output_path: pathlib.Path,
        output_timestep: Union[int, float],
        end_time: Union[int, float],
        resolution: Optional[Union[int, float]] = None,
        mask: Union[int, float] = 9999,
        gpu_device: int = 0,
        small_nc: int = 0) -> None:
    """
    Run the BG-Flood Model for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    model_output_path : pathlib.Path
        The new file path for saving the BG Flood model output with the current timestamp included in the filename.
    output_timestep : Union[int, float]
        Time step between model outputs in seconds. If the value is set to 0 then no output is generated.
    end_time : Union[int, float]
        Time in seconds when the model stops. If the value is set to 0 then the model initializes but does not run.
    resolution : Optional[Union[int, float]] = None
        The grid resolution in meters for metric grids, representing the size of each grid cell.
        If not provided (default is None), the resolution of the Hydrologically conditioned DEM will be used as
        the grid resolution.
    mask : Union[int, float] = 9999
        The mask value is used to remove blocks from computation where the topography elevation (zb) is greater than
        the specified value. Default value is 9999.0 (no areas are masked).
    gpu_device : int = 0
        Specify the GPU device to be used. Default value is 0 (the first available GPU).
        Set the value to -1 to use the CPU. For other GPUs, use values 2 and above.
    small_nc : int = 0
        Specify whether the output should be saved as short integers to reduce the size of the output file.
        Set the value to 1 to enable short integer conversion, or set it to 0 to save all variables as floats.
        Default value is 0.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get the valid BG-Flood Model directory
    bg_flood_dir = get_valid_bg_flood_dir()
    # Get the file path of the Hydro DEM for the catchment area
    hydro_dem_path_str, _, _, dem_resolution = get_dem_by_geometry(engine, catchment_area)
    hydro_dem_path = pathlib.Path(hydro_dem_path_str)
    # Use dem_resolution if input resolution is not provided
    resolution = dem_resolution if resolution is None else resolution

    # Prepare inputs for the BG-Flood Model
    prepare_bg_flood_model_inputs(
        bg_flood_dir=bg_flood_dir,
        model_output_path=model_output_path,
        hydro_dem_path=hydro_dem_path,
        resolution=resolution,
        output_timestep=output_timestep,
        end_time=end_time,
        mask=mask,
        gpu_device=gpu_device,
        small_nc=small_nc)

    # Get the current working directory (cwd)
    cwd = pathlib.Path.cwd()
    # Change the current working directory to the BG-Flood Model directory
    os.chdir(bg_flood_dir)
    # Run the BG-Flood Model executable, accounting for OS differences
    operating_system = platform.system()
    if operating_system == "Windows":
        # Run the .exe
        subprocess.run([bg_flood_dir / "BG_flood.exe"], check=True)
    elif operating_system == "Linux":
        # Run the executable linux script
        subprocess.run([bg_flood_dir / "BG_Flood"], check=True)
    else:
        # Other OSs are not officially supported, but we can attempt to try the Linux one.
        log.warning(f"{operating_system} is not officially supported. Only Windows and Linux are officially supported.")
        log.warning(f"Attempting to run BG_Flood linux script in {operating_system}")
        subprocess.run([bg_flood_dir / "BG_Flood"], check=True)
    # Change the current working directory back to the original directory (cwd)
    os.chdir(cwd)
    log.info(f"Saved new flood model to {model_output_path}")


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        output_timestep: Union[int, float],
        end_time: Union[int, float],
        resolution: Optional[Union[int, float]] = None,
        mask: Union[int, float] = 9999,
        gpu_device: int = 0,
        small_nc: int = 0,
        log_level: LogLevel = LogLevel.DEBUG) -> int:
    """
    Generate BG-Flood model output for the requested catchment area, and incorporate the model output to GeoServer
    for visualization.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    output_timestep : Union[int, float]
        Time step between model outputs in seconds. If the value is set to 0 then no output is generated.
    end_time : Union[int, float]
        Time in seconds when the model stops. If the value is set to 0 then the model initializes but does not run.
    resolution : Optional[Union[int, float]] = None
        The grid resolution in meters for metric grids, representing the size of each grid cell.
        If not provided (default is None), the resolution of the Hydrologically conditioned DEM will be used as
        the grid resolution.
    mask : Union[int, float] = 9999
        The mask value is used to remove blocks from computation where the topography elevation (zb) is greater than
        the specified value. Default value is 9999.0 (no areas are masked).
    gpu_device : int = 0
        Specify the GPU device to be used. Default value is 0 (the first available GPU).
        Set the value to -1 to use the CPU. For other GPUs, use values 2 and above.
    small_nc : int = 0
        Specify whether the output should be saved as short integers to reduce the size of the output file.
        Set the value to 1 to enable short integer conversion, or set it to 0 to save all variables as floats.
        Default value is 0.
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
    int
       Returns the model id of the new flood_model produced
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # Get a new file path for saving the BG Flood model output with the current timestamp included in the filename
    model_output_path = get_new_model_output_path()

    # Run the BG-Flood Model for the specified catchment area
    run_bg_flood_model(
        engine=engine,
        catchment_area=catchment_area,
        model_output_path=model_output_path,
        output_timestep=output_timestep,  # Saving the outputs after each `outputtimestep` seconds
        end_time=end_time,  # Saving the outputs till `endtime` number of seconds
        resolution=resolution,
        mask=mask,
        gpu_device=gpu_device,
        small_nc=small_nc
    )

    # Store metadata related to the BG Flood model output in the database
    model_id = store_model_output_metadata_to_db(engine, model_output_path, catchment_area)
    # Add CRS to the latest BG-Flood model output
    add_crs_to_model_output(engine, model_id)
    # Find buildings that are flooded to a depth greater than or equal to 0.1m
    log.info("Analysing flooded buildings")
    flooded_buildings = find_flooded_buildings(engine, catchment_area, model_output_path, flood_depth_threshold=0.1)
    log.info("Analysed flooded buildings - adding flooded buildings to database")
    store_flooded_buildings_in_database(engine, flooded_buildings, model_id)
    # Add the model output to GeoServer for visualization
    add_model_output_to_geoserver(model_output_path, model_id)
    return model_id


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        output_timestep=100,
        end_time=900,
        resolution=None,
        mask=9999,
        gpu_device=0,
        small_nc=0,
        log_level=LogLevel.DEBUG
    )
