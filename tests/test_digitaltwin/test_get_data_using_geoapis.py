import unittest

from src.digitaltwin import get_data_using_geoapis


class TestFetchVectorDataUsingGeoApis(unittest.TestCase):

    def test_fetch_vector_data_unsupported_provider(self):
        # Test raising ValueError for an unsupported data provider
        with self.assertRaises(ValueError):
            get_data_using_geoapis.fetch_vector_data_using_geoapis("UnknownProvider", 1)


if __name__ == '__main__':
    unittest.main()
