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
from typing import List

import pandas as pd
import numpy as np

from src.dynamic_boundary_conditions.rainfall import hyetograph


class HyetographTest(unittest.TestCase):
    """Tests for hyetograph.py."""

    @classmethod
    def setUpClass(cls):
        """Get all relevant data and set up default arguments used for testing."""
        data_dir = "tests/test_dynamic_boundary_conditions/rainfall/data"
        cls.rain_depth_in_catchment = pd.read_csv(f"{data_dir}/rain_depth_in_catchment.txt")
        cls.transposed_catchment_data = pd.read_csv(f"{data_dir}/transposed_catchment_data.txt")
        cls.interp_catchment_data = pd.read_csv(f"{data_dir}/interp_catchment_data.txt")
        cls.interp_increment_data = pd.read_csv(f"{data_dir}/interp_increment_data.txt")
        cls.storm_length_data = pd.read_csv(f"{data_dir}/storm_length_data.txt")
        cls.site_data_alt_block = pd.read_csv(f"{data_dir}/site_data_alt_block.txt")
        cls.site_data_chicago = pd.read_csv(f"{data_dir}/site_data_chicago.txt")
        cls.hyetograph_depth_alt_block = pd.read_csv(f"{data_dir}/hyetograph_depth_alt_block.txt")
        cls.hyetograph_depth_chicago = pd.read_csv(f"{data_dir}/hyetograph_depth_chicago.txt")
        cls.hyetograph_data_alt_block = pd.read_csv(f"{data_dir}/hyetograph_data_alt_block.txt")
        cls.hyetograph_data_chicago = pd.read_csv(f"{data_dir}/hyetograph_data_chicago.txt")

        cls.increment_mins = 10
        cls.interp_method = "cubic"
        cls.storm_length_mins = 2880
        cls.time_to_peak_mins = 1440
        cls.hyeto_method_alt_block = hyetograph.HyetoMethod.ALT_BLOCK
        cls.hyeto_method_chicago = hyetograph.HyetoMethod.CHICAGO

    def test_get_transposed_data_correct_site_ids(self):
        """Test to ensure correct rainfall site ids after transposition."""
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        orig_site_ids = self.rain_depth_in_catchment["site_id"].to_list()
        tps_site_ids = transposed_catchment_data.columns[1:].to_list()
        self.assertEqual(orig_site_ids, tps_site_ids)

    def test_get_transposed_data_correct_duration_mins(self):
        """Test to ensure correct duration mins after transposition."""
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        org_duration_mins = []
        for column_name in self.rain_depth_in_catchment.columns:
            if column_name[0].isdigit():
                if column_name.endswith("m"):
                    org_duration_mins.append(int(column_name[:-1]))
                elif column_name.endswith("h"):
                    org_duration_mins.append(int(column_name[:-1]) * 60)
        trans_duration_mins = transposed_catchment_data["duration_mins"].to_list()
        self.assertEqual(org_duration_mins, trans_duration_mins)

    def test_get_transposed_data_correct_corner_values(self):
        """Test to ensure correct rainfall data values after transposition."""
        original_data = self.rain_depth_in_catchment.drop(
            columns=["site_id", "category", "rcp", "time_period", "ari", "aep"])
        orig_top_left = original_data.iloc[0][0]
        orig_top_right = original_data.iloc[0][-1]
        orig_bottom_left = original_data.iloc[-1][0]
        orig_bottom_right = original_data.iloc[-1][-1]
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        transposed_data = transposed_catchment_data.drop(columns="duration_mins")
        tps_top_left = transposed_data.iloc[0][0]
        tps_top_right = transposed_data.iloc[0][-1]
        tps_bottom_left = transposed_data.iloc[-1][0]
        tps_bottom_right = transposed_data.iloc[-1][-1]
        self.assertEqual(orig_top_left, tps_top_left)
        self.assertNotEqual(orig_top_right, tps_top_right)
        self.assertNotEqual(orig_bottom_left, tps_bottom_left)
        self.assertEqual(orig_bottom_right, tps_bottom_right)
        self.assertEqual(orig_top_right, tps_bottom_left)
        self.assertEqual(orig_bottom_left, tps_top_right)

    def test_get_interpolated_data_invalid_increment_mins(self):
        """Test to ensure ValueError is raised when 'increment_mins' is invalid."""
        increment_mins_list = list(range(0, 10)) + list(range(7201, 7211))
        for increment_mins in increment_mins_list:
            with self.assertRaises(ValueError) as context:
                hyetograph.get_interpolated_data(
                    self.transposed_catchment_data, increment_mins=increment_mins, interp_method=self.interp_method)
            self.assertEqual(
                f"Increment minute {increment_mins} is out of range, needs to be between 10 and 7200.",
                str(context.exception))

    def test_get_interpolated_data_invalid_interp_method(self):
        """Test to ensure ValueError is raised when 'interp_method' is invalid."""
        interp_method_list = ["invalid", "test", "abc", "123"]
        for interp_method in interp_method_list:
            with self.assertRaises(ValueError) as context:
                hyetograph.get_interpolated_data(
                    self.transposed_catchment_data, increment_mins=self.increment_mins, interp_method=interp_method)
            self.assertEqual(
                f"Invalid interpolation method: '{interp_method}'. "
                f"Refer to 'scipy.interpolate.interp1d()' for available methods.",
                str(context.exception))

    def test_get_interpolated_data_valid_mins_and_method(self):
        """Test to ensure returned data is not empty when valid 'increment_mins' and 'interp_method' are used."""
        increment_mins_list = list(range(10, 7201))
        for increment_mins in increment_mins_list:
            interp_catchment_data = hyetograph.get_interpolated_data(
                self.transposed_catchment_data, increment_mins=increment_mins, interp_method=self.interp_method)
            self.assertGreater(len(interp_catchment_data), 0)

    def test_get_interp_incremental_data_correct_shape(self):
        """Test to ensure returned data have correct number of rows and columns."""
        interp_increment_data = hyetograph.get_interp_incremental_data(self.interp_catchment_data)
        self.assertEqual(self.interp_catchment_data.shape, interp_increment_data.shape)

    def test_get_interp_incremental_data_correct_row_difference(self):
        """Test to ensure returned data have correct row differences, i.e. correct interpolated incremental data."""

        def get_interp_catchment_data_row_difference(index: int) -> List[float]:
            """
            Return interpolated catchment data row difference between selected row and its previous row.

            Parameters
            ----------
            index : int
                An integer number specifying the index position of the selected row.
            """
            if index == 0:
                row_diff = self.interp_catchment_data.iloc[index]
            else:
                row_diff = (self.interp_catchment_data.iloc[index] - self.interp_catchment_data.iloc[index - 1])
                row_diff["duration_mins"] = self.interp_catchment_data.iloc[index]["duration_mins"]
            return row_diff.to_list()

        interp_increment_data = hyetograph.get_interp_incremental_data(self.interp_catchment_data)
        for row_index in range(len(interp_increment_data)):
            expected_row = get_interp_catchment_data_row_difference(index=row_index)
            actual_row = interp_increment_data.iloc[row_index].to_list()
            self.assertEqual(expected_row, actual_row)

    def test_get_storm_length_increment_data_invalid_storm_length_mins(self):
        """Test to ensure ValueError is raised when 'storm_length_mins' is invalid."""
        min_storm_length_mins = self.interp_increment_data["duration_mins"].iloc[0]
        storm_lengths_mins_list = list(range(0, min_storm_length_mins))
        for storm_lengths_mins in storm_lengths_mins_list:
            with self.assertRaises(ValueError) as context:
                hyetograph.get_storm_length_increment_data(
                    self.interp_increment_data, storm_length_mins=storm_lengths_mins)
            self.assertEqual(
                f"Storm duration (storm_length_mins) needs to be at least '{int(min_storm_length_mins)}'.",
                str(context.exception))

    def test_get_storm_length_increment_data_valid_storm_length_mins(self):
        """Test to ensure returned data is not empty when valid 'storm_length_mins' is used."""
        min_storm_length_mins = self.interp_increment_data["duration_mins"].iloc[0]
        storm_lengths_mins_list = range(min_storm_length_mins, 7261)
        for storm_lengths_mins in storm_lengths_mins_list:
            storm_length_data = hyetograph.get_storm_length_increment_data(
                self.interp_increment_data, storm_length_mins=storm_lengths_mins)
            self.assertGreater(len(storm_length_data), 0)

    def test_get_storm_length_increment_data_correct_rows(self):
        """Test to ensure the correct number of rows are returned when valid 'storm_length_mins' is used."""
        min_storm_mins = self.interp_increment_data["duration_mins"].iloc[0]
        max_storm_mins = self.interp_increment_data["duration_mins"].iloc[-1]
        storm_lengths_mins_list = range(min_storm_mins, 7261)
        for storm_lengths_mins in storm_lengths_mins_list:
            if storm_lengths_mins > max_storm_mins:
                expected_row = max_storm_mins // self.increment_mins
            else:
                expected_row = storm_lengths_mins // self.increment_mins
            storm_length_data = hyetograph.get_storm_length_increment_data(
                self.interp_increment_data, storm_length_mins=storm_lengths_mins)
            self.assertEqual(expected_row, len(storm_length_data))

    def test_add_time_information_invalid_time_to_peak_mins(self):
        """Test to ensure ValueError is raised when 'time_to_peak_mins' is invalid."""
        combined_list = [(self.site_data_alt_block, self.hyeto_method_alt_block),
                         (self.site_data_chicago, self.hyeto_method_chicago)]
        min_time_to_peak_mins = int(self.storm_length_mins / 2)
        time_to_peak_mins_list = range(0, min_time_to_peak_mins)
        for site_data, hyeto_method in combined_list:
            for time_to_peak_mins in time_to_peak_mins_list:
                with self.assertRaises(ValueError) as context:
                    hyetograph.add_time_information(
                        site_data=site_data,
                        storm_length_mins=self.storm_length_mins,
                        time_to_peak_mins=time_to_peak_mins,
                        increment_mins=self.increment_mins,
                        hyeto_method=hyeto_method)
                self.assertEqual(
                    "'time_to_peak_mins' (time in minutes when rainfall is at its greatest) needs to be "
                    "at least half of 'storm_length_mins' (storm duration).",
                    str(context.exception))

    def test_add_time_information_increment_mins_correct_increment_mins_diff(self):
        """Test to ensure returned data have correct consistent increment minutes difference."""
        combined_list = [(self.site_data_alt_block, self.hyeto_method_alt_block),
                         (self.site_data_chicago, self.hyeto_method_chicago)]
        for site_data, hyeto_method in combined_list:
            site_data_output = hyetograph.add_time_information(
                site_data=site_data,
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            mins = site_data_output["mins"].to_list()
            mins_diff = np.unique(np.diff(mins))
            if hyeto_method == "alt_block":
                self.assertEqual(self.increment_mins, mins_diff)
            else:
                self.assertEqual(self.increment_mins / 2, mins_diff)

    def test_add_time_information_correct_time_calculation(self):
        """Test to ensure returned data have correct time calculations."""
        combined_list = [(self.site_data_alt_block, self.hyeto_method_alt_block),
                         (self.site_data_chicago, self.hyeto_method_chicago)]
        for site_data, hyeto_method in combined_list:
            site_data_output = hyetograph.add_time_information(
                site_data=site_data,
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            for row_index in range(len(site_data_output)):
                row = site_data_output.iloc[row_index]
                self.assertEqual(row["mins"] / 60, row["hours"])
                self.assertEqual(row["mins"] * 60, row["seconds"])
                if row_index == 0:
                    if hyeto_method == "alt_block":
                        self.assertEqual(self.increment_mins, row["mins"])
                    else:
                        self.assertEqual(self.increment_mins / 2, row["mins"])

    @patch("src.dynamic_boundary_conditions.rainfall.hyetograph.get_storm_length_increment_data")
    def test_transform_data_for_selected_method_correct_columns_and_storm_length(self, mock_storm_length_data):
        """Test to ensure returned data have correct columns and storm length."""
        mock_storm_length_data.return_value = self.storm_length_data
        hyeto_method_list = [self.hyeto_method_alt_block, self.hyeto_method_chicago]
        for hyeto_method in hyeto_method_list:
            hyetograph_depth = hyetograph.transform_data_for_selected_method(
                interp_increment_data=pd.DataFrame(),
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            expected_columns = list(self.interp_increment_data.columns[1:]) + ["mins", "hours", "seconds"]
            actual_columns = hyetograph_depth.columns.tolist()
            self.assertEqual(expected_columns, actual_columns)
            expected_storm_length = self.storm_length_mins
            actual_storm_length = hyetograph_depth["mins"].iloc[-1]
            self.assertEqual(expected_storm_length, actual_storm_length)

    @patch("src.dynamic_boundary_conditions.rainfall.hyetograph.get_storm_length_increment_data")
    def test_transform_data_for_selected_method_correct_layout_and_rows(self, mock_storm_length_data):
        """Test to ensure returned data have correct output layout and number of rows."""
        mock_storm_length_data.return_value = self.storm_length_data
        hyeto_method_list = [self.hyeto_method_alt_block, self.hyeto_method_chicago]
        for hyeto_method in hyeto_method_list:
            hyetograph_depth = hyetograph.transform_data_for_selected_method(
                interp_increment_data=pd.DataFrame(),
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            first_row = hyetograph_depth.iloc[0, :-3]
            last_row = hyetograph_depth.iloc[-1, :-3]
            if hyeto_method == "alt_block":
                # check that first row and last row does not match
                with self.assertRaises(AssertionError):
                    pd.testing.assert_series_equal(first_row, last_row, check_names=False)
                # check the number of returned rows
                self.assertEqual(len(mock_storm_length_data.return_value), len(hyetograph_depth))
            else:
                # check that first row and last row match
                pd.testing.assert_series_equal(first_row, last_row, check_names=False)
                # check the number of returned rows
                self.assertEqual(len(mock_storm_length_data.return_value) * 2, len(hyetograph_depth))

    def test_hyetograph_depth_to_intensity_correct_conversion(self):
        """Test to ensure hyetograph data have been correctly converted from 'depths' to 'intensities'."""
        combined_list = [(self.hyetograph_depth_alt_block, self.hyeto_method_alt_block),
                         (self.hyetograph_depth_chicago, self.hyeto_method_chicago)]
        for hyetograph_depth, hyeto_method in combined_list:
            hyetograph_intensity = hyetograph.hyetograph_depth_to_intensity(
                hyetograph_depth=hyetograph_depth,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)

            duration_interval = self.increment_mins if hyeto_method == "alt_block" else (self.increment_mins / 2)
            for row_index in range(len(hyetograph_depth)):
                sites_intensity = hyetograph_depth.iloc[row_index, :-3] / duration_interval * 60
                sites_time = hyetograph_depth.iloc[row_index, -3:]
                expected_hyetograph_intensity = pd.concat([sites_intensity, sites_time])
                pd.testing.assert_series_equal(expected_hyetograph_intensity, hyetograph_intensity.iloc[row_index])

    def test_hyetograph_depth_to_intensity_correct_layout_and_rows(self):
        """Test to ensure returned data have correct output layout and number of rows."""
        combined_list = [(self.hyetograph_depth_alt_block, self.hyeto_method_alt_block),
                         (self.hyetograph_depth_chicago, self.hyeto_method_chicago)]
        for hyetograph_depth, hyeto_method in combined_list:
            hyetograph_intensity = hyetograph.hyetograph_depth_to_intensity(
                hyetograph_depth=hyetograph_depth,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            first_row = hyetograph_intensity.iloc[0, :-3]
            last_row = hyetograph_intensity.iloc[-1, :-3]
            if hyeto_method == "alt_block":
                # check that first row and last row does not match
                with self.assertRaises(AssertionError):
                    pd.testing.assert_series_equal(first_row, last_row, check_names=False)
                    # check the number of returned rows
                self.assertEqual(len(hyetograph_depth), len(hyetograph_intensity))
            else:
                # check that first row and last row match
                pd.testing.assert_series_equal(first_row, last_row, check_names=False)
                # check the number of returned rows
                self.assertEqual(len(hyetograph_depth), len(hyetograph_intensity))

    def test_hyetograph_data_wide_to_long_correct_transposition(self):
        """Test to ensure transposed data have correct information as the original."""
        hyetograph_data_list = [self.hyetograph_data_alt_block, self.hyetograph_data_chicago]
        for hyetograph_data in hyetograph_data_list:
            hyetograph_data_long = hyetograph.hyetograph_data_wide_to_long(hyetograph_data)
            site_ids = hyetograph_data.drop(columns=["mins", "hours", "seconds"]).columns.to_list()
            self.assertEqual(site_ids, hyetograph_data_long["site_id"].unique().tolist())
            for site_id in site_ids:
                site_data = hyetograph_data_long.query(f"site_id == '{site_id}'")
                self.assertEqual(hyetograph_data["mins"].tolist(), site_data["mins"].tolist())
                self.assertEqual(hyetograph_data["hours"].tolist(), site_data["hours"].tolist())
                self.assertEqual(hyetograph_data["seconds"].tolist(), site_data["seconds"].tolist())
                self.assertEqual(hyetograph_data[f"{site_id}"].tolist(), site_data["rain_intensity_mmhr"].tolist())

    def test_hyetograph_data_wide_to_long_correct_rows(self):
        """Test to ensure transposed data have correct number of rows."""
        hyetograph_data_list = [self.hyetograph_data_alt_block, self.hyetograph_data_chicago]
        for hyetograph_data in hyetograph_data_list:
            hyetograph_data_long = hyetograph.hyetograph_data_wide_to_long(hyetograph_data)
            site_ids = hyetograph_data.drop(columns=["mins", "hours", "seconds"]).columns.tolist()
            self.assertEqual(len(hyetograph_data) * len(site_ids), len(hyetograph_data_long))


if __name__ == "__main__":
    unittest.main()
