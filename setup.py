#!/usr/bin/env python3
from distutils.core import setup
from monoscript import VERSION

with open('README.md', 'r') as f:
    long_description = f.read()

with open('LICENSE', 'r') as f:
    license_text = f.read()

if __name__ == "__main__":
    setup(
        name='monoscript',
        version=VERSION,
        description='A Python tool that merges multi-file modules into a single, self-contained script.',
        long_description=long_description,
        long_description_content_type='text/markdown',
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
        install_requires=['PyYAML'],
        python_requires='>=3',
        packages=['monoscript'],
        package_data={
            '': ['LICENSE', 'requirements.txt', 'README.md'],
        },
    )