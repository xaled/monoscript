from monoscript import PythonModuleMerger
from setup import VERSION, DESCRIPTION, URL, load_requirements

if __name__ == '__main__':
    PythonModuleMerger(
        module_path='monoscript',
        module_version=VERSION,
        requirements=load_requirements() or ['None'],
        module_description=DESCRIPTION,
        author='Khalid Grandi https://github.com/xaled',
        license='MIT License Copyright (c) 2025 Khalid Grandi',
        project_website=URL

    ).merge_files()

