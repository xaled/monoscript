from monoscript import PythonModuleMerger, VERSION

if __name__ == '__main__':
    PythonModuleMerger(
        module_path='monoscript',
        module_version=VERSION,
        module_description='A Python tool that merges multi-file modules into a single, self-contained script',
        author='Khalid Grandi https://github.com/xaled',
        license='MIT License Copyright (c) 2025 Khalid Grandi',
        project_website='https://github.com/xaled/monoscript'

    ).merge_files()

