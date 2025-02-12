import os
import sys

# Top-level import (standard)
import math as matho

# Top-level import (from)
from collections import Counter, defaultdict as dd

# Top-level import (as)
import numpy as np

# Conditional import (inside if statement)
if __name__ == "__main__":
    import datetime

    # Conditional import (inside if statement, from)
    from pathlib import Path

    # Conditional import (inside if statement, as)
    import random as rnd


def my_function(arg1, arg2="default", *args, **kwargs):
    """
    Function with imports inside.
    """
    # Import inside a function
    import json
    global my_var
    a, b, (c, d) = 1, 2, (3, 4)

    if arg1 > 10:
        # Import inside a conditional block within a function
        import hashlib

        print("arg1 is greater than 10")
        result = arg1 * 2

        # Import inside a conditional block within a function (from)
        from typing import List

        my_list: List[int] = [1, 2, 3]  # Example of type hint using imported List

    elif arg1 == 10:
        result = arg1 + 5
    else:
        result = arg1 ** 2

    for i in range(5):
        nonlocal result
        # Import inside a loop
        from uuid import uuid4
        print(f"Value: {i} - UUID: {uuid4()}")

    try:
        value = kwargs['key']
    except KeyError:
        value = "default_value"

    if arg1:
        def sub_func():
            pass

        class SubClass:
            pass

    return result


class MyClass:
    """
    A simple class.
    """

    def __init__(self, value):
        self.value = value

    def my_method(self, other_value):
        """
        A method in MyClass.
        """
        # Import inside a method
        import time

        start_time = time.time()
        result = self.value + other_value
        end_time = time.time()
        print(f"Method execution time: {end_time - start_time}")
        return result


# Another function with different structure
def another_function(x, y):
    """
    Another function.
    """
    if x > y:
        return x - y
    elif x < y:
        return y - x
    else:
        return 0


# Example Usage
if __name__ == "__main__":
    my_var = 20
    my_function(my_var, arg2="new_value", extra=1, another=2)
    my_instance = MyClass(100)
    print(my_instance.my_method(50))

    # Example of using the conditionally imported modules
    now = datetime.datetime.now()
    print(f"Current date and time: {now}")

    my_path = Path("./some_file.txt")  # Example usage of Path
    print(f"Path exists: {my_path.exists()}")

    random_number = rnd.randint(1, 10)  # Example of using imported random as rnd
    print(f"Random number: {random_number}")

    # Example of using modules imported inside the function
    import json  # This import is redundant at the top level, but it's here for demonstration

    data = {"name": "Example", "age": 30}
    json_string = json.dumps(data)
    print(json_string)

    # Internal module import (assuming 'my_module.py' is in the same directory)
    try:
        import my_module  # Example of an internal module import

        my_module.my_internal_function()
    except ImportError:
        print("my_module not found.  Create my_module.py in the same directory to test.")
