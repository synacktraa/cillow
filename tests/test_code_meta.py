import ast
from types import CodeType

import pytest

from cillow.code_meta import CodeMeta, compile_code


def test_empty_code():
    """Test handling of empty code string"""
    code = ""
    meta = CodeMeta.from_code(code)
    assert meta.module_names == set()
    assert meta.to_exec is None
    assert meta.to_eval is None


def test_simple_expression():
    """Test handling of a simple expression"""
    meta = CodeMeta.from_code("42")
    assert meta.module_names == set()
    assert meta.to_exec is None
    assert isinstance(meta.to_eval, CodeType)
    assert eval(meta.to_eval) == 42  # noqa: S307


def test_import_extraction():
    """Test extraction of module imports"""
    code = """
import os
from pathlib import Path
import sys as system
from datetime import datetime as dt
    """
    meta = CodeMeta.from_code(code)
    assert meta.module_names == {"os", "pathlib", "sys", "datetime"}
    assert isinstance(meta.to_exec, CodeType)
    assert meta.to_eval is None


def test_mixed_code():
    """Test code with both executable statements and final expression"""
    code = """
x = 10
y = 20
x + y
    """
    meta = CodeMeta.from_code(code)
    assert meta.module_names == set()
    assert isinstance(meta.to_exec, CodeType)
    assert isinstance(meta.to_eval, CodeType)

    namespace = {}
    exec(meta.to_exec, namespace)  # noqa: S102
    assert namespace["x"] == 10
    assert namespace["y"] == 20
    assert eval(meta.to_eval, namespace) == 30  # noqa: S307


def test_invalid_eval():
    """Test code that can't be evaluated"""
    code = """
x = 10
import math  # Import statements can't be evaluated
    """
    meta = CodeMeta.from_code(code)
    assert meta.module_names == {"math"}
    assert isinstance(meta.to_exec, CodeType)
    assert meta.to_eval is None


@pytest.mark.parametrize("filename", ["<string>", "test.py", "/path/to/file.py"])
def test_different_filenames(filename):
    """Test handling of different filenames"""
    code = "print('hello')"
    meta = CodeMeta.from_code(code, filename=filename)
    assert isinstance(meta.to_eval, CodeType)
    assert meta.to_eval.co_filename == filename


def test_ast_module_creation():
    """Test creation from AST module directly"""
    module = ast.parse("x = 42\nx + 1")
    meta = CodeMeta.from_ast_module(module)
    assert meta.module_names == set()
    assert isinstance(meta.to_exec, CodeType)
    assert isinstance(meta.to_eval, CodeType)


def test_complex_imports():
    """Test handling of complex import patterns"""
    code = """
from os import path
from sys import version as py_version
import json, pickle
from datetime import (
    datetime,
    timezone
)
    """
    meta = CodeMeta.from_code(code)
    assert meta.module_names == {"os", "sys", "json", "pickle", "datetime"}
    assert isinstance(meta.to_exec, CodeType)
    assert meta.to_eval is None


def test_compile_code_function():
    """Test the compile_code function directly"""
    code_str = "x = 42"
    compiled = compile_code(code_str, "<string>", "exec")
    assert isinstance(compiled, CodeType)

    module = ast.parse(code_str)
    compiled = compile_code(module, "<string>", "exec")
    assert isinstance(compiled, CodeType)


@pytest.mark.parametrize(
    "code,expected_eval",
    [
        ("42", True),
        ("x = 42", False),
        ("'hello'", True),
        ("def func(): pass", False),
        ("(x for x in range(10))", True),
        ("class Test: pass", False),
    ],
)
def test_various_expressions(code: str, expected_eval: bool):
    """Test handling of various types of expressions"""
    meta = CodeMeta.from_code(code)
    if expected_eval:
        assert meta.to_eval is not None
    else:
        assert meta.to_eval is None


def test_error_handling():
    """Test handling of invalid code"""
    with pytest.raises(SyntaxError):
        CodeMeta.from_code("this is not valid python")


def test_frozen_dataclass():
    """Test that CodeMeta instances are immutable"""
    meta = CodeMeta.from_code("42")
    with pytest.raises(AttributeError):
        meta.module_names = set()
