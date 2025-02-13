import sys
import unittest
import os

from module4 import util_function  # noqa
import random


class Module4TestCase2(unittest.TestCase):

    def test_util_function(self):
        for _ in range(10):
            a = random.randint(0, 100)
            b = random.randint(0, 100)

            self.assertEqual(a + b, util_function(a, b))


if __name__ == '__main__':
    unittest.main()
