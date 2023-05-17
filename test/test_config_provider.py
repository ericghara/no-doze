from unittest import TestCase

from src import config_provider


class TestConfigProvider(TestCase):

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_get_value_key_exists(self):
        yml_str ="""
        test:
            key: "found"
        """
        config_provider._load_string(yml_str)
        found = config_provider.get_value(["test","key"], "not_found")
        self.assertEqual("found", found)

    def test_get_value_parent_not_exists_key_not_exists_returns_default(self):
        yml_str = """
                """
        expected = "default"
        config_provider._load_string(yml_str)
        found = config_provider.get_value(["test","key"], expected)
        self.assertEqual(expected, found)

    def test_get_value_parent_exists_key_not_exists_return_default(self):
        yml_str = """
        test:
            wrong-key: "don't find me"
        """
        expected = "default"
        config_provider._load_string(yml_str)
        found = config_provider.get_value(["test", "key"], expected)
        self.assertEqual(expected, found)

    def test_get_value_key_not_exists_raises_when_no_default(self):
        yml_str = """
                """
        config_provider._load_string(yml_str)
        self.assertRaises(ValueError, lambda: config_provider.get_value(["test","key"]) )

    def test_get_value_raises_when_value_non_scalar(self):
        yml_str = """
        a:
            b: 
                c: true
        """
        config_provider._load_string(yml_str)
        self.assertRaises(ValueError, lambda: config_provider.get_value(["test","key"]))

    def test_get_value_raises_when_key_path_is_not_list(self):
        self.assertRaises(ValueError, lambda: config_provider.get_value("abc"))

    def test_key_exists_key_does_not_exist(self):
        yml_str = """
        test:
            keyyyyyyy: "oops typo" 
        """
        config_provider._load_string(yml_str)
        self.assertFalse(config_provider.key_exists(["test", "key"]))

    def test_key_exists_key_does_exist(self):
        yml_str = """
        test:
            key: "I EXIST!" 
        """
        config_provider._load_string(yml_str)
        self.assertTrue(config_provider.key_exists(["test", "key"]))


