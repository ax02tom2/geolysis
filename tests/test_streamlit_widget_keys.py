"""Static regression test: every number_input in app.py must have an explicit, non-colliding key."""
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATHS = [ROOT / "app.py", *sorted((ROOT / "geolysis_ui").glob("module*.py"))]


def test_all_number_inputs_have_explicit_unique_keys():
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in APP_PATHS]
    key_expressions = []
    missing = []

    for tree in trees:
      for node in ast.walk(tree):
          if not (
              isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == "number_input"
          ):
              continue
  
          key_node = next((kw.value for kw in node.keywords if kw.arg == "key"), None)
          # Literal strings, f-strings, and named variables are valid explicit keys.
          # Streamlit evaluates f-strings and variables at runtime; requiring a literal
          # incorrectly rejects intentionally unique keys based on selected geology.
          if key_node is None or not isinstance(
              key_node, (ast.Constant, ast.JoinedStr, ast.Name)
          ):
              missing.append(node.lineno)
              continue
          if isinstance(key_node, ast.Constant) and (
              not isinstance(key_node.value, str) or not key_node.value
          ):
              missing.append(node.lineno)
              continue
          key_expressions.append(ast.dump(key_node, include_attributes=False))
  
    assert not missing, f"number_input missing an explicit key at lines: {missing}"
    assert len(key_expressions) == len(set(key_expressions)), (
        f"duplicate number_input key expressions: {key_expressions}"
    )
