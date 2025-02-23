#!/usr/bin/env python3
from setuptools import setup
from monoscript import VERSION
import os
# from m2r2 import convert
import pypandoc


def load_requirements(requirements_file="requirements.txt"):
    try:
        with open(requirements_file, 'r') as fin:
            requirements = [line.split('#')[0].strip() for line in fin]
            requirements = [line for line in requirements if line]
        return requirements
    except FileNotFoundError:
        print(f"Requirements file '{requirements_file}' not found.")
        return []
    except Exception as e:
        print(f"Error loading requirements: {e}")
        return []


# with open('README.md', 'r') as f:
#     long_description = f.read()

long_description = pypandoc.convert_file('README.md', 'rst')

# with open('README.md', 'r') as f:
#     long_description = convert(f.read())

with open('LICENSE', 'r') as f:
    license_text = f.read()

if __name__ == "__main__":
    setup(
        name='monoscript',
        version=VERSION,
        description='A Python tool that merges multi-file modules into a single, self-contained script.',
        long_description_content_type="text/x-rst",
        long_description=long_description,
        keywords='packaging python',
        author='Khalid Grandi',
        author_email='kh.grandi@gmail.com',
        classifiers=[
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
        ],
        license='MIT',
        url='https://github.com/xaled/monoscript',
        install_requires=load_requirements(),
        test_suite="tests",
        # tests_require=load_requirements("requirements-test.txt"),
        # dev_require=load_requirements("requirements-dev.txt"),
        python_requires='>=3',
        packages=['monoscript'],
        package_data={
            '': ['LICENSE', 'requirements.txt', 'README.md'],
        },
    )
