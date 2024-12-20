# Copyright © 2023-2024 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE

import unittest

import numpy as np
from geopandas import GeoDataFrame

from src.flood_model.flooded_buildings import categorise_buildings_as_flooded


class CategoriseBuildingsAsFloodedTest(unittest.TestCase):

    def setUp(self) -> None:
        data_dir = "tests/test_flood_model/data"
        self.flood_polygons = GeoDataFrame.from_file(f"{data_dir}/flood_polygon_test.geojson")
        self.building_polygons = GeoDataFrame.from_file(f"{data_dir}/flood_building_test.geojson")

    def test_correct_flooded_buildings(self):
        """
        Tests a series of cases of non-flooded and flooded buildings.
        Check the labels in self.building_polygons to see the details of each case
        """
        flooded_gdf = categorise_buildings_as_flooded(self.building_polygons, self.flood_polygons)

        correct_flood_categories = np.array([False, True, True, True, True]) # To understand the values of this array, check the labels in the file supplied by self.building_polygons
        self.assertTrue((flooded_gdf["is_flooded"].values == correct_flood_categories).all())


if __name__ == "__main__":
    unittest.main()
