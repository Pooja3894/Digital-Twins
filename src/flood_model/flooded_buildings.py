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

import pathlib

import geopandas as gpd
import pandas as pd
import rasterio as rio
import shapely
import xarray
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.flood_model.serve_model import create_building_database_views_if_not_exists


def store_flooded_buildings_in_database(engine: Engine, buildings: pd.DataFrame, flood_model_id: int) -> None:
    """
    Appends the details of which buildings are flooded for a given flood_model_id to the database

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    buildings : pd.DataFrame
        DataFrame containing a mapping of building_ids to their flood status for the current model run
    flood_model_id : float
        The id of the current flood model run, to associate with the building flood data.

    Returns
    -------
    None
        This function does not return anything
    """
    # Associate the building flood status dataframe with the current model id
    buildings["flood_model_id"] = flood_model_id
    # Append the dataframe to the database
    buildings.to_sql("building_flood_status", engine, if_exists="append", index=True)
    # Create geoserver endpoints for database views if they do not already exist
    create_building_database_views_if_not_exists()


def find_flooded_buildings(engine: Engine,
                           area_of_interest: gpd.GeoDataFrame,
                           flood_model_output_path: pathlib.Path,
                           flood_depth_threshold: float) -> pd.DataFrame:
    """
    Creates a building DataFrame with attribute "is_flooded",
    depending on if the area for each building is flooded to a depth greater than or equal to flood_depth_threshold.
    the index, building_outline_id, matches building_outline_id from nz_building_outline table.

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame with a polygon specifying the area to get buildings for.
    flood_model_output_path : pathlib.Path
        Path to the flood model output file to be read.
    flood_depth_threshold : float
        The minimum depth required to designate a pixel in the raster as flooded.

    Returns
    -------
    pd.DataFrame
        A pd.DataFrame specifying if each building is flooded or not.
    """
    # Open flood output and read the maximum depth raster
    with xarray.open_dataset(flood_model_output_path, decode_coords="all") as ds:
        max_depth_raster = ds["hmax_P0"]
    # Find areas flooded in a polygon format, if they are deeper than flood_depth_threshold
    thresholded_flood_polygons = polygonize_flooded_area(max_depth_raster, flood_depth_threshold)
    # Get building outlines from database
    buildings = retrieve_building_outlines(engine, area_of_interest)
    # Categorise buildings as flooded or not flooded
    return categorise_buildings_as_flooded(buildings, thresholded_flood_polygons)


def categorise_buildings_as_flooded(building_polygons: gpd.GeoDataFrame,
                                    flood_polygons: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies all buildings in building_polygons that intersect with areas in flooded_polygons.

    Parameters
    ----------
    building_polygons : gpd.GeoDataFrame
        A GeoDataFrame with each polygon representing a building outline
    flood_polygons : gpd.GeoDataFrame
        A GeoDataFrame with each polygon representing a flooded area

    Returns
    -------
    gpd.GeoDataFrame
        A copy of building_polygons with an additional boolean attribute "is_flooded"
    """
    # Create a joined GeoDataFrame with each building, and any flood polygons they intersect
    building_status = gpd.sjoin(left_df=building_polygons, right_df=flood_polygons, how="left",
                                predicate="intersects")
    # Add is_flooded attribute to each building
    building_status["is_flooded"] = ~building_status["index_right"].isnull()
    # Remove extraneous information about what flood polygon is flooding the building and geometry information
    # that is duplicated in nz_building_outlines table
    building_status.drop(['index_right', 'geometry'], axis=1, inplace=True)
    # Remove duplicates created when a building is flooded by multiple different flood polygons
    filtered_buildings = building_status[~building_status.index.duplicated(keep='first')]
    return filtered_buildings


def retrieve_building_outlines(engine: Engine, area_of_interest: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve building outlines for an area of interest from the database

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame polygon specifying the area of interest to retrieve buildings in.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing all of the building outlines in the area
    """
    # Get the area of interest polygon in well known text format for database querying
    aoi_wkt = area_of_interest["geometry"][0].wkt
    crs = area_of_interest.crs.to_epsg()
    # Construct the query to find buildings within the area of interest
    command_text = """
    SELECT building_outline_id, geometry FROM nz_building_outlines
    WHERE ST_INTERSECTS(nz_building_outlines.geometry, ST_GeomFromText(:aoi_wkt, :crs));
    """
    query = text(command_text).bindparams(
        aoi_wkt=str(aoi_wkt),
        crs=str(crs)
    )
    # Execute the query and retrieve the result as a GeoDataFrame
    gdf = gpd.GeoDataFrame.from_postgis(query, engine, index_col="building_outline_id", geom_col="geometry")
    return gdf


def polygonize_flooded_area(flood_raster: xarray.DataArray, flood_depth_threshold: float) -> gpd.GeoDataFrame:
    """
    Takes a flood depth raster and applies depth thresholding on it so that only areas
    flooded deeper than or equal to flood_depth_threshold are represented.
    Returns the data in a collection of polygons

    Parameters
    ----------
    flood_raster : xarray.DataArray
        Raster with each pixel representing flood depth at the point
    flood_depth_threshold : float
        The minimum depth specified to consider a pixel in the raster flooded

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing polygons of the flooded areas
    """
    # Find areas that are flooded to at least the flood_depth_threshold depth
    mask = flood_raster >= flood_depth_threshold
    # Turn the flood mask into a vector polygon form
    flood_polygons = rio.features.shapes(flood_raster, mask=mask, transform=flood_raster.rio.transform())
    polygons_records = []
    # Add each polygon to a list in a form ready to be ingested into a GeoDataFrame to be returned
    for polygon, _h in flood_polygons:
        shapely_poly = shapely.Polygon(polygon['coordinates'][0])
        new_row = {"geometry": shapely_poly}
        polygons_records.append(new_row)
    return gpd.GeoDataFrame(polygons_records, crs=flood_raster.rio.crs.wkt)
