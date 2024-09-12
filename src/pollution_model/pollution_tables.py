"""This script contains a SQLAlchemy model for the medusa 2.0 database table."""
import abc
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeMeta


class _DeclarativeABCMeta(DeclarativeMeta, abc.ABCMeta):
    """Metaclass to allow abstract base class to be used with a declarative base."""


# Base for standard tables
Base = declarative_base()
# Base for AbstractBaseClass tables
ABCMetaBase = declarative_base(metaclass=_DeclarativeABCMeta)


class _BaseMedusa2ModelOutput(ABCMetaBase):
    """
    Abstract Base Class (abc) representing each of 'medusa_2_model_output' tables.

    Attributes
    ----------
    scenario_id : int
        The rainfall event scenario ID this feature was processed with, makes up part of the primary key.
    surface_type : str
        The type of surface this is. Converted to string from Enum.
    total_suspended_solids : float
        Total suspended solids of the surface.
    total_copper : float
        Total copper of the surface.
    total_zinc: float
        Total zinc of the surface.
    dissolved_copper float
        Total dissolved copper of the surface.
    dissolved_zinc: float
        Total dissolved zinc of the surface.
    """

    __abstract__ = True  # This is an abstract base class

    @property
    @abc.abstractmethod
    def __tablename__(self) -> str:
        """
        Name of the database table.
        This must be overridden in the child class. e.g. __tablename__ = "medusa2_model_output_buildings."

        Returns
        ----------
        str
            The name of the database table.
        """
        raise NotImplementedError("""__tablename__ must be overridden in the child class.
                                  e.g. __tablename__ = "medusa2_model_output_buildings". """)

    @property
    @abc.abstractmethod
    def geometry_table(self) -> str:
        """
        Name of the spatial feature table this table is associated with.
        This must be overridden in the child class. e.g. geometry_table = "nz_buildings".

        Returns
        ----------
        str
            The name of the spatial feature table this table is associated with.
        """
        raise NotImplementedError("""geometry_table must be overridden in the child class.
                                  e.g. geometry_table = "nz_buildings". """)

    @property
    @abc.abstractmethod
    def spatial_feature_id(self) -> int:
        """
        The ID of the spatial feature this row is associated with, makes up part of the primary key.
        This must be overridden in the child class.
        e.g. spatial_feature_id = Column(Integer, primary_key=True, name="building_id").

        Returns
        ----------
        int
            The ID of the spatial feature this row is associated with.
        """
        raise NotImplementedError("""spatial_feature_id must be overridden in the child class.
                                  eg. spatial_feature_id = Column(Integer, primary_key=True, name="building_id"). """)

    scenario_id = Column(Integer, primary_key=True)
    surface_type = Column(String, nullable=False)
    total_suspended_solids = Column(Float, nullable=False)
    total_copper = Column(Float, nullable=False)
    total_zinc = Column(Float, nullable=False)
    dissolved_copper = Column(Float, nullable=False)
    dissolved_zinc = Column(Float, nullable=False)


class Medusa2ModelOutputBuildings(_BaseMedusa2ModelOutput):
    """
    Class representing the medusa2_model_output_buildings table.

    Attributes
    ----------
    __tablename__ : str
       Name of the database table.
    geometry_table : str
        Name of the spatial feature table this table is associated with (nz_building_outlines).
    spatial_feature_id: int
        The building_id this row is associated with, makes up part of the primary key.
    scenario_id : int
        The rainfall event scenario ID this feature was processed with, makes up part of the primary key.
    surface_type : str
        The type of surface this is. Converted to string from Enum.
    total_suspended_solids : float
        Total suspended solids of the surface.
    total_copper : float
        Total copper of the surface.
    total_zinc: float
        Total zinc of the surface.
    dissolved_copper float
        Total dissolved copper of the surface.
    dissolved_zinc: float
        Total dissolved zinc of the surface.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa2_model_output_buildings"
    geometry_table = "nz_building_outlines"
    spatial_feature_id = Column(Integer, primary_key=True, name="building_id")


class Medusa2ModelOutputRoads(_BaseMedusa2ModelOutput):
    """
    Class representing the medusa2_model_output_roads table.

    Attributes
    ----------
    __tablename__ : str
       Name of the database table.
    geometry_table : str
        Name of the spatial feature table this table is associated with (nz_roads).
    spatial_feature_id: int
        The road_id this row is associated with, makes up part of the primary key.
    scenario_id : int
        The rainfall event scenario ID this feature was processed with, makes up part of the primary key.
    surface_type : str
        The type of surface this is. Converted to string from Enum.
    total_suspended_solids : float
        Total suspended solids of the surface.
    total_copper : float
        Total copper of the surface.
    total_zinc: float
        Total zinc of the surface.
    dissolved_copper float
        Total dissolved copper of the surface.
    dissolved_zinc: float
        Total dissolved zinc of the surface.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa2_model_output_roads"
    geometry_table = "nz_roads"
    spatial_feature_id = Column(Integer, primary_key=True, name="road_id")


class MedusaScenarios(Base):
    """
    Class representing the 'MedusaUserLogInfo' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    scenario_id: int
        Returns the model id of the new flood_model produce
    antecedent_dry_days: float
        The number of dry days between rainfall events.
    average_rain_intensity: float
        The intensity of the rainfall event in mm/h.
    event_duration: float
        The number of hours of the rainfall event.
    rainfall_ph: float
        The pH level of the rainfall, a measure of acidity.
    created_at : datetime
        Timestamp indicating when the log entry was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa_scenarios"
    scenario_id = Column(Integer, primary_key=True, autoincrement=True)

    antecedent_dry_days = Column(Float, primary_key=True)
    average_rain_intensity = Column(Float, primary_key=True)
    event_duration = Column(Float, primary_key=True)
    rainfall_ph = Column(Float, primary_key=True)

    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="log created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))
