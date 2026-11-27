"""Every word the package prints, logs, or raises keeps Telureo's punctuation rule: no em dashes and no semicolons,
which read as machine-written."""
import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "edu_subnet"


def strings(file: pathlib.Path):
    """The file's string literals, without its docstrings (those are comments in the code)."""
    tree = ast.parse(file.read_text(), str(file))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.lineno, node.value


def test_no_em_dash_or_semicolon_in_what_people_read():
    broken = [f"{file.relative_to(SOURCE)}:{line}  {' '.join(text.split())[:120]}"
              for file in sorted(SOURCE.rglob("*.py")) for line, text in strings(file) if "—" in text or ";" in text]
    assert not broken, "Use a comma, plain words, or two sentences:\n" + "\n".join(broken)
