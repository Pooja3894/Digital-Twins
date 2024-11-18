import shutil
import tempfile
import unittest

import geopandas as gpd
from geojson import Point
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.digitaltwin.tables import RiverNetworkExclusions, RiverNetwork
from src.dynamic_boundary_conditions.river.river_network_to_from_db import (
    add_network_exclusions_to_db
)


class TestRainNetworkToFromDB(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for data
        self.temp_dir = tempfile.mkdtemp()
        # Create a temporary SQLite database in memory
        self.engine = create_engine('sqlite:///:memory:')
        # Create tables
        RiverNetwork.metadata.create_all(self.engine)
        RiverNetworkExclusions.metadata.create_all(self.engine)
        # Create a session
        session = sessionmaker(bind=self.engine)
        self.session = session()

    def tearDown(self):
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_add_network_exclusions_to_db(self):
        # Create a sample GeoDataFrame for testing
        rec_network_exclusions = gpd.GeoDataFrame(
            dict(objectid=[1, 2, 3], geometry=[Point(0, 0), Point(1, 1), Point(2, 2)]))
        rec_network_id = 1
        exclusion_cause = "Test Cause"
        # Test if the function runs without errors
        add_network_exclusions_to_db(self.engine, rec_network_id, rec_network_exclusions, exclusion_cause)

        # Query the database and check if the data is inserted
        result = self.session.query(RiverNetworkExclusions).filter_by(rec_network_id=rec_network_id).all()
        self.assertEqual(len(result), len(rec_network_exclusions))


if __name__ == '__main__':
    unittest.main()
