import unittest

import geopandas as gpd
import pandas as pd
from shapely.wkt import loads

from src.dynamic_boundary_conditions.tide import tide_data_from_niwa


class TideDataFromNiwaTest(unittest.TestCase):
    query_loc_row = None

    @classmethod
    def setUpClass(cls):
        data_dir = "tests/test_dynamic_boundary_conditions/tide/data"
        cls.query_loc_row = pd.read_csv(f"{data_dir}/query_loc_row.csv")
        cls.query_loc_row['geometry'] = cls.query_loc_row['geometry'].apply(loads)
        cls.gdf = gpd.GeoDataFrame(cls.query_loc_row, geometry='geometry')

    def test_get_query_loc_coords_position(self):
        actual_output = tide_data_from_niwa.get_query_loc_coords_position(self.gdf)
        expected_output = (-43.39127633722616, 172.7098878483352, 'right')
        self.assertEqual(actual_output, expected_output)

    def test_invalid_total_days_get_date_ranges(self):
        # Test with total_days less than 1
        with self.assertRaises(ValueError):
            tide_data_from_niwa.get_date_ranges(total_days=0)

    def test_invalid_days_per_call_get_date_ranges(self):
        # Test with days_per_call greater than 31
        with self.assertRaises(ValueError):
            tide_data_from_niwa.get_date_ranges(days_per_call=32)

        # Test with days_per_call less than 1
        with self.assertRaises(ValueError):
            tide_data_from_niwa.get_date_ranges(days_per_call=0)


if __name__ == "__main__":
    unittest.main()
