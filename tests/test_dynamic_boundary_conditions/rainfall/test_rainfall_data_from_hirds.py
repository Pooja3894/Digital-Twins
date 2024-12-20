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
import pathlib
from typing import List, Optional
import math

import pandas as pd

from src.dynamic_boundary_conditions.rainfall import rainfall_data_from_hirds


class RainfallDataFromHirdsTest(unittest.TestCase):
    """Tests for rainfall_data_from_hirds.py."""

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

    @staticmethod
    def get_block_structures(
            depth_layout: List[rainfall_data_from_hirds.BlockStructure],
            intensity_layout: List[rainfall_data_from_hirds.BlockStructure],
            start: Optional[int] = None,
            end: Optional[int] = None) -> List[rainfall_data_from_hirds.BlockStructure]:
        """
        Get a list of BlockStructures from both depth and intensity layouts.

        Parameters
        ----------
        depth_layout : List[rainfall_data_from_hirds.BlockStructure]
            Fetched rainfall depths data's layout structure.
        intensity_layout : List[rainfall_data_from_hirds.BlockStructure]
            Fetched rainfall intensities data's layout structure.
        start : Optional[int] = None
            An integer number specifying at which position to start the slicing of both depth and intensity layouts.
            Default is None, i.e. omitting the start index, starts the slice from index 0.
        end : Optional[int] = None
            An integer number specifying at which position to end the slicing of both depth and intensity layouts.
            Default is None, i.e. omitting the end index, extends the slice to the end of the list.
        """
        layout_structures = (depth_layout[start:end], intensity_layout[start:end])
        block_structures = []
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                block_structures.append(block_structure)
        return block_structures

    @classmethod
    def setUpClass(cls):
        """Get rainfall depths and intensities data and their layout structures for site 323605."""
        data_dir = "tests/test_dynamic_boundary_conditions/rainfall/data"
        cls.rainfall_depth = cls.open_file(f"{data_dir}/rainfall_depth.txt")
        cls.rainfall_intensity = cls.open_file(f"{data_dir}/rainfall_intensity.txt")
        cls.depth_historical = cls.open_file(f"{data_dir}/depth_historical.txt")

        cls.depth_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.rainfall_depth)
        cls.intensity_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.rainfall_intensity)
        cls.depth_hist_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.depth_historical)

        cls.example_site_id = "323605"

    def test_get_layout_structure_of_data_correct_blocks(self):
        """Test to ensure the right number of blocks or BlockStructures are returned."""
        self.assertEqual(10, len(self.depth_layout))
        self.assertEqual(10, len(self.intensity_layout))
        self.assertEqual(1, len(self.depth_hist_layout))

    def test_get_layout_structure_of_data_correct_data_types(self):
        """Test to ensure the arguments in each BlockStructure are of the correct data type."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout)
        for block_structure in block_structures:
            self.assertIsInstance(block_structure.skip_rows, int)
            self.assertIsInstance(block_structure.rcp, float)
            self.assertIsInstance(block_structure.time_period, (type(None), str))
            self.assertIsInstance(block_structure.category, str)

    def test_get_layout_structure_of_data_rcp_nan(self):
        """Test to ensure that rcp is nan for the first two BlockStructures in both depth and intensity layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, end=2)
        for block_structure in block_structures:
            self.assertTrue(math.isnan(block_structure.rcp))

    def test_get_layout_structure_of_data_rcp_not_nan(self):
        """Test to ensure that rcp is not nan for the rest of the BlockStructures (i.e., except the first two
        BlockStructures) in both depth and intensity layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, start=2)
        for block_structure in block_structures:
            self.assertFalse(math.isnan(block_structure.rcp))

    def test_get_layout_structure_of_data_time_period_none(self):
        """Test to ensure that time period is None for the first two BlockStructures in both depth and intensity
        layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, end=2)
        for block_structure in block_structures:
            self.assertIsNone(block_structure.time_period)

    def test_get_layout_structure_of_data_time_period_not_none(self):
        """Test to ensure that time period is not None for the rest of the BlockStructures (i.e., except the first
        two BlockStructures) in both depth and intensity layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, start=2)
        for block_structure in block_structures:
            self.assertIsNotNone(block_structure.time_period)

    def test_get_layout_structure_of_data_category_hist(self):
        """Test to ensure that category is 'hist' for the first BlockStructure in both depth and intensity layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, end=1)
        for block_structure in block_structures:
            self.assertEqual("hist", block_structure.category)

    def test_get_layout_structure_of_data_category_hist_stderr(self):
        """Test to ensure that category is 'hist_stderr' for the second BlockStructure in both depth and intensity
        layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, start=1, end=2)
        for block_structure in block_structures:
            self.assertEqual("hist_stderr", block_structure.category)

    def test_get_layout_structure_of_data_category_proj(self):
        """Test to ensure that category is 'proj' for the rest of the BlockStructure (i.e., except the first two
        BlockStructures) in both depth and intensity layouts."""
        block_structures = self.get_block_structures(self.depth_layout, self.intensity_layout, start=2)
        for block_structure in block_structures:
            self.assertEqual("proj", block_structure.category)

    def test_convert_to_tabular_data_correct_frame_type(self):
        """Test that each block of rainfall depths and intensities data has been converted to a DataFrame."""
        site_data = [self.rainfall_depth, self.rainfall_intensity, self.depth_historical]
        layout_structure = [self.depth_layout, self.intensity_layout, self.depth_hist_layout]

        for i in range(len(site_data)):
            for block_structure in layout_structure[i]:
                rain_table = rainfall_data_from_hirds.convert_to_tabular_data(
                    site_data[i], self.example_site_id, block_structure)
                self.assertIsInstance(rain_table, pd.DataFrame)

    def test_convert_to_tabular_data_correct_rows_columns(self):
        """Test that each converted DataFrame contains the same correct number of rows and columns."""
        site_data = [self.rainfall_depth, self.rainfall_intensity, self.depth_historical]
        layout_structure = [self.depth_layout, self.intensity_layout, self.depth_hist_layout]

        for i in range(len(site_data)):
            for block_structure in layout_structure[i]:
                rain_table = rainfall_data_from_hirds.convert_to_tabular_data(
                    site_data[i], self.example_site_id, block_structure)
                self.assertEqual((12, 18), rain_table.shape)

    def test_get_site_url_key_not_empty(self):
        """Test to ensure that the site url key for both rainfall depths and intensities data fetched from
        the HIRDS website is not empty."""
        site_url_key_depth = rainfall_data_from_hirds.get_site_url_key(self.example_site_id, idf=False)
        site_url_key_intensity = rainfall_data_from_hirds.get_site_url_key(self.example_site_id, idf=True)
        self.assertGreater(len(site_url_key_depth), 0)
        self.assertGreater(len(site_url_key_intensity), 0)

    def test_get_data_from_hirds_not_empty(self):
        """Test to ensure that the rainfall depths and intensities data fetched from the HIRDS website is not empty."""
        depth_data = rainfall_data_from_hirds.get_data_from_hirds(self.example_site_id, idf=False)
        intensity_data = rainfall_data_from_hirds.get_data_from_hirds(self.example_site_id, idf=True)
        self.assertGreater(len(depth_data), 0)
        self.assertGreater(len(intensity_data), 0)


if __name__ == "__main__":
    unittest.main()
