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

import os
import unittest

import pytest
from sqlalchemy.exc import OperationalError

from src import config
from src.digitaltwin import setup_environment


class SetupEnvironmentTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up arguments used for testing."""
        # flag for checking if tests requiring database to be active should run
        cls.run_database_integration_tests = config.get_env_variable("TEST_DATABASE_INTEGRATION",
                                                                     default=True,
                                                                     allow_empty=True,
                                                                     cast_to=bool
                                                                     )
        cls.DATABASE_SKIP_REASON = """TEST_DATABASE_INTEGRATION env var is not True, so the test is skipped.
            This is intentional at all times on the GitHub Actions."""

    def test_connection(self):
        """Check a connection to the database can be made with the default parameters of get_connection_from_profile"""
        # Skip this if database tests are not intended to be run in this environment
        if not self.run_database_integration_tests:
            pytest.skip(self.DATABASE_SKIP_REASON)
        engine = setup_environment.get_connection_from_profile()
        connection = engine.connect()
        self.assertFalse(connection.closed,
                         msg="The connection to the database failed and is needed for these tests.")

    def test_incorrect_password(self):
        """Ensure that when a bad password is given to the database, the connection fails and an exception is raised"""
        # Skip this if database tests are not intended to be run in this environment
        if not self.run_database_integration_tests:
            pytest.skip(self.DATABASE_SKIP_REASON)
        self.test_connection()  # This test case requires an active connection to trust the result.
        # Override the variables supplied by the .env file with an incorrect password
        os.environ["POSTGRES_PASSWORD"] = "incorrect_password"
        with self.assertRaises(OperationalError,
                               msg="get_connection_from_profile should raise an OperationalError"
                                   " if the password supplied is incorrect"):
            setup_environment.get_connection_from_profile()


if __name__ == '__main__':
    unittest.main()
