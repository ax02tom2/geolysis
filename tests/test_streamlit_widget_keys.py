"""Static regression test: every number_input in app.py must have a unique key."""
import ast
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_all_number_inputs_have_unique_explicit_keys():
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    keys = []
    missing = []

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "number_input"
        ):
            continue

        key_node = next((kw.value for kw in node.keywords if kw.arg == "key"), None)
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            missing.append(node.lineno)
            continue
        keys.append(key_node.value)

    assert not missing, f"number_input missing a literal key at lines: {missing}"
    assert len(keys) == len(set(keys)), f"duplicate number_input keys: {keys}"
