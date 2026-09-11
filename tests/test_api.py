import unittest

from remnawave_updater.api import RemnawaveAPI


class TestRemnawaveAPI(unittest.TestCase):
    def test_extract_nodes_from_nested_response(self):
        payload = {
            "response": {
                "nodes": [
                    {"uuid": "1", "name": "DE", "address": "1.2.3.4", "isConnected": True},
                    {"uuid": "2", "name": "NL", "address": "node.example.com", "isConnected": False},
                ]
            }
        }
        rows = RemnawaveAPI._extract_node_dicts(payload)
        self.assertEqual(len(rows), 2)
        node = RemnawaveAPI._to_node(rows[0])
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "DE")
        self.assertEqual(node.host, "1.2.3.4")
        self.assertIs(node.is_connected, True)

    def test_base_url_adds_api_once(self):
        api = RemnawaveAPI("https://panel.example.com", "token")
        self.assertEqual(api.base_url, "https://panel.example.com/api")
        api = RemnawaveAPI("https://panel.example.com/api", "token")
        self.assertEqual(api.base_url, "https://panel.example.com/api")


if __name__ == "__main__":
    unittest.main()
