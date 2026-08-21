from fixtures.coding_agent.AGENT_CODE_005.pipeline import prepare_items


def test_prepare_items_removes_empty_values_and_trims():
    assert prepare_items([" a ", "", "b"]) == ["a", "b"]


def test_prepare_items_preserves_current_order():
    assert prepare_items(["b", "a", "b"]) == ["b", "a", "b"]
