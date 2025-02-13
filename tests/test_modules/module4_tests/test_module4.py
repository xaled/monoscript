import sys
import unittest
import os

from module4 import core_function  # noqa
import random


class TestPythonModuleMerger(unittest.TestCase):

    def test_core_function(self):
        for _ in range(10):
            a = random.randint(0, 100)
            b = random.randint(0, 100)

            self.assertEqual(a + b, core_function(a, b))


if __name__ == '__main__':
    unittest.main()
