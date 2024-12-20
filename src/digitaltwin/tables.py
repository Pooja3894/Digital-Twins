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
This script contains SQLAlchemy models for various database tables and utility functions for database operations.
"""

from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, inspect, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.schema import CheckConstraint, PrimaryKeyConstraint

Base = declarative_base()


class GeospatialLayers(Base):
    """
    Class representing the 'geospatial_layers' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each geospatial layer entry (primary key).
    data_provider : str
        Name of the data provider.
    layer_id : int
        Identifier for the layer.
    table_name : str
        Name of the table containing the data.
    unique_column_name : Optional[str]
        Name of the unique column in the table.
    coverage_area : Optional[str]
        Coverage area of the geospatial data, e.g. 'New Zealand'.
    url : str
        URL pointing to the geospatial layer.
    """
    __tablename__ = "geospatial_layers"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    data_provider = Column(String, nullable=False)
    layer_id = Column(Integer, nullable=False)
    table_name = Column(String, nullable=False)
    unique_column_name = Column(String, nullable=True)
    coverage_area = Column(String, nullable=True)
    url = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "((unique_column_name IS NOT NULL AND coverage_area IS NULL) OR "
            "(unique_column_name IS NULL AND coverage_area IS NOT NULL))",
            name="unique_column_name_or_coverage_area_required"
        ),
    )


class UserLogInfo(Base):
    """
    Class representing the 'user_log_information' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each log entry (primary key).
    source_table_list : Dict[str]
        A list of tables (geospatial layers) associated with the log entry.
    created_at : datetime
        Timestamp indicating when the log entry was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """
    __tablename__ = "user_log_information"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    source_table_list = Column(ARRAY(String), comment="associated tables (geospatial layers)")
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="log created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


class RiverNetworkExclusions(Base):
    """
    Class representing the 'rec_network_exclusions' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    rec_network_id : int
        An identifier for the river network associated with each new run.
    objectid : int
        An identifier for the REC river object matching from the 'rec_data' table.
    exclusion_cause : str
        Cause of exclusion, i.e., the reason why the REC river geometry was excluded.
    geometry : LineString
        Geometric representation of the excluded REC river features.
    """
    __tablename__ = "rec_network_exclusions"
    rec_network_id = Column(Integer, primary_key=True,
                            comment="An identifier for the river network associated with each run")
    objectid = Column(Integer, primary_key=True,
                      comment="An identifier for the REC river object matching from the 'rec_data' table")
    exclusion_cause = Column(String, comment="Cause of exclusion")
    geometry = Column(Geometry("LINESTRING", srid=2193))

    __table_args__ = (
        PrimaryKeyConstraint('rec_network_id', 'objectid', name='network_exclusions_pk'),
    )


class RiverNetwork(Base):
    """
    Class representing the 'rec_network' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    rec_network_id : int
        An identifier for the river network associated with each new run (primary key).
    network_path : str
        Path to the REC river network file.
    network_data_path : str
        Path to the REC river network data file for the AOI.
    created_at : datetime
        Timestamp indicating when the output was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """
    __tablename__ = "rec_network"
    rec_network_id = Column(Integer, primary_key=True,
                            comment="An identifier for the river network associated with each run")
    network_path = Column(String, comment="path to the rec river network file")
    network_data_path = Column(String, comment="path to the rec river network data file for the AOI")
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="output created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


class BGFloodModelOutput(Base):
    """
    Class representing the 'bg_flood_model_output' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each entry (primary key).
    file_name : str
        Name of the flood model output file.
    file_path : str
        Path to the flood model output file.
    created_at : datetime
        Timestamp indicating when the output was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """
    __tablename__ = "bg_flood_model_output"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, comment="name of the flood model output file")
    file_path = Column(String, comment="path to the flood model output file")
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="output created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


class BuildingFloodStatus(Base):
    """
    Class representing the 'building_flood_status' table.
    Represents if a building is flooded for a given flood model output

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each entry (primary key).
    building_outline_id : int
        Foreign key building outline id matching from nz_building_outlines table
    is_flooded : bool
        If the building is flooded or not
    flood_model_id: int.
        Foreign key mathing the unique_id from bg_flood_model_output table
    """
    __tablename__ = "building_flood_status"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    building_outline_id = Column(Integer, comment="The building outline id matching from nz_building_outlines table")
    is_flooded = Column(Boolean, comment="If the building is flooded or not")
    flood_model_id = Column(Integer)


def create_table(engine: Engine, table: Base) -> None:
    """
    Create a table in the database if it doesn't already exist, using the provided engine.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    table : Base
        Class representing the table to create.

    Returns
    -------
    None
        This function does not return any value.
    """
    table.__table__.create(bind=engine, checkfirst=True)


def check_table_exists(engine: Engine, table_name: str, schema: str = "public") -> bool:
    """
    Check if a table exists in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    table_name : str
        The name of the table to check for existence.
    schema : str = "public"
        The name of the schema where the table resides. Defaults to "public".

    Returns
    -------
    bool
        True if the table exists, False otherwise.
    """
    inspector = inspect(engine)
    return inspector.has_table(table_name, schema=schema)


def execute_query(engine: Engine, query) -> None:
    """
    Execute the given query on the provided engine using a session.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    query
        The query to be executed.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    Exception
        If an error occurs during the execution of the query.
    """
    with Session(engine) as session:
        session.begin()
        try:
            session.add(query)
            session.commit()
        except Exception as error:
            session.rollback()
            raise error
