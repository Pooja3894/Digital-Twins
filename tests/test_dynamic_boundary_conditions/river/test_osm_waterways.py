import unittest

import geopandas as gpd
import pandas as pd

from src.dynamic_boundary_conditions.river import osm_waterways


class OsmWaterwaysTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data_dir = "tests/test_dynamic_boundary_conditions/river/data"
        cls.catchment_area = pd.read_csv(f"{data_dir}/catchment_area.txt")

    def test_fetch_osm_waterways(self):
        gdf_catchment_area = gpd.GeoDataFrame(self.catchment_area, geometry='geometry', crs='EPSG:4326')
        result_osm_waterways = osm_waterways.fetch_osm_waterways(gdf_catchment_area)
        self.assertIsInstance(result_osm_waterways, gpd.GeoDataFrame)
        self.assertSetEqual(set(osm_waterways.columns), {'id', 'waterway', 'geometry'})
        self.assertEqual(result_osm_waterways.crs, self.catchment_area.crs)
