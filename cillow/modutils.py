from __future__ import annotations

import ast
from importlib.metadata import distributions

MODULE_TO_PACKAGE_MAP = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "dotenv": "python-dotenv",
    "PIL": "pillow",
    "psycopg2": "psycopg2-binary",
    "sklearn": "scikit-learn",
    "tk": "tkinter",
    "wx": "wxPython",
    "yaml": "pyyaml",
    "zmq": "pyzmq",
}
"""Mapping of modules to packages that don't have the same name"""


class _ImportVisitor(ast.NodeVisitor):
    """Internal class for extracting module names from an AST module"""

    def __init__(self) -> None:
        self.module_names: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.module_names.add(alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self.module_names.add(node.module.split(".")[0])

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)

        for stmt in node.body:
            self.visit(stmt)

        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)

    def visit_Try(self, node: ast.Try) -> None:
        for stmt in node.body:
            self.visit(stmt)

        for handler in node.handlers:
            for stmt in handler.body:
                self.visit(stmt)

        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)

        if node.finalbody:
            for stmt in node.finalbody:
                self.visit(stmt)


def extract_modules_from_ast_module(__mod: ast.Module) -> set[str]:
    """
    Extract the module names from an AST module.

    Args:
        __mod: The AST module to extract module names from

    Returns:
        Set of module names
    """
    visitor = _ImportVisitor()
    visitor.visit(__mod)
    return visitor.module_names


def extract_modules_from_code(__code: str) -> set[str]:
    """
    Extract the module names from code string.

    Args:
        __code: The code string to extract module names from

    Returns:
        Set of module names
    """
    return extract_modules_from_ast_module(ast.parse(__code))


def get_installed_modules() -> set[str]:
    """
    Get all installed module names.

    Returns:
        Set of module names
    """

    modules = set()
    for dist in distributions():
        try:
            if top_level := dist.read_text("top_level.txt"):
                modules.update(top_level.splitlines())
            else:
                modules.add(dist.name)
        except Exception:  # noqa: S112
            continue

    return modules
