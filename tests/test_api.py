from remnawave_updater.api import RemnawaveAPI


def test_extract_nodes_from_nested_response():
    payload = {
        "response": {
            "nodes": [
                {"uuid": "1", "name": "DE", "address": "1.2.3.4", "isConnected": True},
                {"uuid": "2", "name": "NL", "address": "node.example.com", "isConnected": False},
            ]
        }
    }
    rows = RemnawaveAPI._extract_node_dicts(payload)
    assert len(rows) == 2
    node = RemnawaveAPI._to_node(rows[0])
    assert node.name == "DE"
    assert node.host == "1.2.3.4"
    assert node.is_connected is True


def test_base_url_adds_api_once():
    api = RemnawaveAPI("https://panel.example.com", "token")
    assert api.base_url == "https://panel.example.com/api"
    api = RemnawaveAPI("https://panel.example.com/api", "token")
    assert api.base_url == "https://panel.example.com/api"
