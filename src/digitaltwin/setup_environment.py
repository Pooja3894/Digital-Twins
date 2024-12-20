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
This script provides functions to set up the database connection using SQLAlchemy and environment variables,
as well as to create an SQLAlchemy engine for database operations.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError

from src import config

log = logging.getLogger(__name__)

Base = declarative_base()


def get_database() -> Engine:
    """
    Set up the database connection. Exit the program if connection fails.

    Returns
    -------
    Engine
        The engine used to connect to the database.

    Raises
    ------
    OperationalError
        If the connection to the database fails.
    """
    try:
        engine = get_connection_from_profile()
        log.debug("Connected to PostgreSQL database successfully!")
        return engine
    except OperationalError as e:
        raise OperationalError("Database connection failed. Please check database running and check .env file.") from e


def get_connection_from_profile() -> Engine:
    """
    Sets up database connection from configuration.

    Returns
    -------
    Engine
        The engine used to connect to the database.

    Raises
    ------
    ValueError
        If one or more connection credentials are missing in the .env file.
    """
    # Get the connection credentials from the environment variables
    connection_keys = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    host, port, db, username, password = (config.get_env_variable(key) for key in connection_keys)
    # Check if any connection credential is missing
    if any(connection_cred is None for connection_cred in [host, port, db, username, password]):
        raise ValueError("Please check the .env file as one or more of the connection credentials are missing.")
    # Create and return the database engine
    return get_engine(host, port, db, username, password)


def get_engine(host: str, port: str, db: str, username: str, password: str) -> Engine:
    """
    Get SQLAlchemy engine using credentials.

    Parameters
    ----------
    host : str
        Hostname of the database server.
    port : str
        Port number.
    db : str
        Database name.
    username : str
        Username.
    password : str
        Password for the database.

    Returns
    -------
    Engine
        The engine used to connect to the database.
    """
    url = f'postgresql://{username}:{password}@{host}:{port}/{db}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine
