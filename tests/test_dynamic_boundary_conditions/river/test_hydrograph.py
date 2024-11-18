import unittest

import geopandas as gpd
import pandas as pd
from shapely import LineString
from shapely.wkt import loads

from src.dynamic_boundary_conditions.river import hydrograph


class HydrographTest(unittest.TestCase):
    rec_inflows_w_input_points_df = None

    @classmethod
    def setUpClass(cls):
        data_dir = "tests/test_dynamic_boundary_conditions/river/data"
        cls.rec_inflows_w_input_points_df = pd.read_csv(f"{data_dir}/rec_inflows_w_input_points.txt")
        cls.rec_inflows_w_input_points_df['start_point'] = cls.rec_inflows_w_input_points_df['first_coord'].apply(loads)
        cls.rec_inflows_w_input_points_df['end_point'] = cls.rec_inflows_w_input_points_df['last_coord'].apply(loads)
        cls.rec_inflows_w_input_points_df['geometry'] = cls.rec_inflows_w_input_points_df.apply(
            lambda row: LineString([row['start_point'], row['end_point']]), axis=1)
        cls.rec_inflows_w_input_points = gpd.GeoDataFrame(cls.rec_inflows_w_input_points_df, geometry='geometry')

    def test_clean_rec_inflow_data_correct_flow_maf(self):
        cleaned_rec_inflow_data = hydrograph.clean_rec_inflow_data(self.rec_inflows_w_input_points)
        orig_flow_maf = self.rec_inflows_w_input_points["h_c18_maf"].to_list()
        cleaned_flow_maf = cleaned_rec_inflow_data["flow_maf"].to_list()
        self.assertEqual(orig_flow_maf, cleaned_flow_maf)

    def test_clean_rec_inflow_data_correct_flow_5h(self):
        cleaned_rec_inflow_data = hydrograph.clean_rec_inflow_data(self.rec_inflows_w_input_points)
        orig_flow_5h = self.rec_inflows_w_input_points["h_c18_5_yr"].to_list()
        cleaned_flow_5h = cleaned_rec_inflow_data["flow_5h"].to_list()
        self.assertEqual(orig_flow_5h, cleaned_flow_5h)


if __name__ == "__main__":
    unittest.main()
