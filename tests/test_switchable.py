import logging
import random
import sys

import pytest

from cillow.switchable import Switchable, switch


def mock_random() -> float:
    return 0.42


def custom_write_1(text: str) -> None:
    logging.error(f"[Logger 1] {text}")


def custom_write_2(text: str) -> None:
    logging.error(f"[Logger 2] {text}")


class TestClass:
    def instance_method(self, x: int) -> int:
        return x * 2

    @classmethod
    def class_method(cls, x: int) -> int:
        return x * 3

    @staticmethod
    def static_method(x: int) -> int:
        return x * 4


def test_stdout_redirection(tmp_path):
    """Test redirecting sys.stdout.write to a file (Example 1)"""
    test_file = tmp_path / "test.txt"
    switchable = Switchable(sys.stdout.write)

    with test_file.open("w") as f, switchable.switch_to(f.write):
        print("This will go into the file!")

    assert test_file.read_text().strip() == "This will go into the file!"


def test_nested_switching(caplog):
    """Test nested switching with re-entrant context managers (Example 2)"""
    switchable = Switchable(sys.stdout.write)

    with caplog.at_level(logging.ERROR), switchable.switch_to(custom_write_1):
        print("Message 1")
        with switchable.switch_to(custom_write_2):
            print("Message 2")
        print("Message 3")

    records = caplog.records
    assert len(records) == 6  # +3 for the new lines
    assert "[Logger 1] Message 1" in records[0].message
    assert "[Logger 2] Message 2" in records[2].message
    assert "[Logger 1] Message 3" in records[4].message


def test_mock_random_choice():
    """Test mocking random.choice for testing (Example 3)"""

    def mock_choice(seq):
        return seq[0]

    switchable = Switchable(random.choice)
    test_list = [1, 2, 3]

    with switchable.switch_to(mock_choice):
        assert random.choice(test_list) == 1

    result = random.choice(test_list)
    assert result in test_list


def test_switch_function():
    """Test the switch context manager function"""
    orig_random = random.random

    with switch(random.random, mock_random) as switchable:
        assert random.random() == 0.42
        assert isinstance(switchable, Switchable)

        with switchable.switch_to(lambda: 0.99):
            assert random.random() == 0.99

    assert random.random != mock_random
    assert random.random == orig_random


def test_instance_method_switching():
    """Test switching instance methods"""
    obj = TestClass()

    def mock_instance_method(self, x: int) -> int:
        return x * 10

    switchable = Switchable(obj.instance_method)

    with switchable.switch_to(mock_instance_method.__get__(obj, TestClass)):
        assert obj.instance_method(5) == 50

    assert obj.instance_method(5) == 10


def test_class_method_switching():
    """Test switching class methods"""

    def mock_class_method(cls, x: int) -> int:
        return x * 20

    switchable = Switchable(TestClass.class_method)

    with switchable.switch_to(classmethod(mock_class_method).__get__(None, TestClass)):
        assert TestClass.class_method(5) == 100

    assert TestClass.class_method(5) == 15


def test_original_property():
    """Test the original property of Switchable"""
    orig_random = random.random
    switchable = Switchable(random.random)

    assert switchable.original == orig_random

    with switchable.switch_to(mock_random):
        assert switchable.original == orig_random

        with switchable.switch_to(lambda: 0.99):
            assert switchable.original == orig_random


def test_module_level_function():
    """Test switching module-level functions"""
    orig_abs = abs

    def mock_abs(x):
        return -x

    with switch(abs, mock_abs):
        assert abs(-5) == 5  # Should still return positive as mock_abs isn't properly bound

    assert abs == orig_abs


def test_multiple_switches():
    """Test multiple switches in sequence"""
    values: list[float] = []
    switchable = Switchable(random.random)

    def mock_1() -> float:
        return 0.1

    def mock_2() -> float:
        return 0.2

    def mock_3() -> float:
        return 0.3

    with switchable.switch_to(mock_1):
        values.append(random.random())
        with switchable.switch_to(mock_2):
            values.append(random.random())
        values.append(random.random())
        with switchable.switch_to(mock_3):
            values.append(random.random())
        values.append(random.random())

    assert values == [0.1, 0.2, 0.1, 0.3, 0.1]


def test_switch_callable_attributes():
    """Test that switched callable maintains original attributes"""

    def original(x: int) -> int:
        """Original docstring"""
        return x

    original.custom_attr = "test"

    def replacement(x: int) -> int:
        return x * 2

    switchable = Switchable(original)

    with switchable.switch_to(replacement):
        assert switchable._current_target == replacement
        assert original.custom_attr == "test"


@pytest.mark.parametrize("exception", [ValueError, TypeError, RuntimeError])
def test_exception_handling(exception):
    """Test that original function is restored even if exception occurs"""
    orig_random = random.random

    def raising_func():
        raise exception("Test error")

    with pytest.raises(exception), switch(random.random, raising_func):
        random.random()

    assert random.random == orig_random
