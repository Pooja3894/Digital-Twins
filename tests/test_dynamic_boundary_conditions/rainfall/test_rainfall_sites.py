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

import unittest
from unittest.mock import patch
import pathlib

import geopandas as gpd

from src.dynamic_boundary_conditions.rainfall import rainfall_sites


class RainfallSitesTest(unittest.TestCase):
    """Tests for rainfall_sites.py."""

    @staticmethod
    def open_file(filepath: str) -> str:
        """
        Read the content of a text data file.

        Parameters
        ----------
        filepath : str
            The file path of the text data file.
        """
        data_file = pathlib.Path(filepath)
        with open(data_file) as in_file:
            file_content = in_file.read()
            return file_content

    @classmethod
    @patch("src.dynamic_boundary_conditions.rainfall.rainfall_sites.get_rainfall_sites_data")
    def setUpClass(cls, mock_sites_data):
        """Get rainfall sites data and convert it to tabular format."""
        data_dir = "tests/test_dynamic_boundary_conditions/rainfall/data"
        mock_sites_data.return_value = cls.open_file(f"{data_dir}/rainfall_sites.txt")
        cls.sites = rainfall_sites.get_rainfall_sites_in_df()

    def test_get_rainfall_sites_in_df_correct_frame_type(self):
        """Test to ensure tabular data is returned in GeoDataFrame format."""
        self.assertIsInstance(self.sites, gpd.GeoDataFrame)

    def test_get_rainfall_sites_in_df_added_geom_column(self):
        """Test to ensure the 'geometry' column was added."""
        column_name = self.sites.columns[-1]
        self.assertEqual("geometry", column_name)

    def test_get_rainfall_sites_data_not_empty(self):
        """Test to ensure that the rainfall sites data fetched from the HIRDS website is not empty."""
        sites_data = rainfall_sites.get_rainfall_sites_data()
        self.assertGreater(len(sites_data), 0)


if __name__ == "__main__":
    unittest.main()
