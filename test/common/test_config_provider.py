from unittest import TestCase

from common import config_provider
from common.config_provider import CastFn


class TestConfigProvider(TestCase):

    def setUp(self) -> None:
        config_provider._load_string("") # clear yaml between tests

    def tearDown(self) -> None:
        pass

    def test_get_value_key_exists(self):
        yml_str ="""
        test:
            key: "found"
        """
        config_provider._load_string(yml_str)
        found = config_provider.get_value(["test", "key"], "not_found")
        self.assertEqual("found", found)

    def test_get_value_parent_not_exists_key_not_exists_returns_default(self):
        yml_str = """
                """
        expected = "default"
        config_provider._load_string(yml_str)
        found = config_provider.get_value(["test", "key"], expected)
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
        self.assertRaises(ValueError, lambda: config_provider.get_value(["test", "key"]))

    def test_get_value_raises_when_value_non_scalar(self):
        yml_str = """
        a:
            b: 
                c: true
        """
        config_provider._load_string(yml_str)
        self.assertRaises(ValueError, lambda: config_provider.get_value(["test", "key"]))

    def test_get_value_raises_when_key_path_is_not_list(self):
        self.assertRaises(ValueError, lambda: config_provider.get_value(["abc"]))

    def test_get_value_casts_when_key_exists(self):
        expected = 3.0
        yaml_str = """
        a: "3"
        """
        config_provider._load_string(yml_str=yaml_str)
        self.assertEqual(expected, config_provider.get_value(["a"],cast_fn=CastFn.to_float))

    def test_get_value_returns_default_when_key_not_exists(self):
        expected = 3.0
        self.assertEqual(expected, config_provider.get_value(["a"], cast_fn=CastFn.to_float, default=3.0))

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

    def test_get_object_when_object_does_exist(self):
        yml_str = """
                test:
                    - 1
                    - 2
                    - 3 
                """
        config_provider._load_string(yml_str)
        self.assertEqual([1,2,3], config_provider.get_object(["test"]))

    def test_get_object_returns_default_when_object_does_not_exist(self):
        yml_str = """
                        test:
                        """
        config_provider._load_string(yml_str)
        self.assertEqual([1, 2, 3], config_provider.get_object(["test"], [1, 2, 3]))

    def test_get_object_raises_when_object_does_not_exist_and_not_default_provided(self):
        yml_str = """
                                test:
                                """
        config_provider._load_string(yml_str)
        self.assertRaises(ValueError, lambda: config_provider.get_object(["test"]))

    def test_get_object_raise_when_key_is_a_scalar(self):
        yml_str = """
                                        test: "is scalar"
                                        """
        config_provider._load_string(yml_str)
        self.assertRaises(ValueError, lambda: config_provider.get_object(["test"]))


