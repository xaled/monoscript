# Monoscript
Monoscript is a Python tool designed to merge multi-file modules into a single, self-contained Python file. This output file can then be used as a portable standalone script/module or included in other projects without the hassle of adding it to the packaging system.
---
## Features
- **Multiple `__all__` Strategies:**
  - **`AUTO`:** Automatically determines `__all__` definitions by combining explicit `__all__` definitions and implicit internal imports from the module's `__init__.py`.
  - **`custom`:** Allows you to set a custom `__all__` definition.
  - **`INIT`:** Takes only the explicit `__all__` definition from `__init__.py`.
  - **`NONE`:** No `__all__` definition is added.
- **Removes Internal Imports:** Internal imports within the module are automatically removed.
- **Organized Imports:** Top-level imports are cleaned up and organized. Redundant imports are removed.
- **Test Scripts Integration:**  Merges and/or runs your test scripts.
- **Metadata Support:** Includes support for metadata such as `author`, `description`, `version`, `requirements`, and more.
---
## Limitations
Monoscript is intended for small modules and should not be used for larger projects. Merging code from multiple files into a single file can cause unwanted behaviors:
- **No Namespaces:** All code is merged into a single file, which may result in global name conflicts. The script warns you if conflicts are detected.
- **Complex Top-Level Imports:** Imports within conditional statements (e.g., `if` statements or `try/except` blocks) are not reorganized and are left as-is.
- **Complex `__all__` Assignments:** Only simple assignments or incremental updates to lists of strings are supported. Complex operations on `__all__` are ignored.
---
## Installation
Install Monoscript using pip:
```bash
pip install monoscript
```
Alternatively, download `monoscript.py` from releases and use it directly.
---
## Usage
### Command Line
Run Monoscript via the command line:
```bash
python -m monoscript path/to/module --output-dir="dist"
```
Or directly:
```bash
python monoscript.py path/to/module --output-dir="dist"
```
Usage:
```
$ python3 monoscript.py --help
usage: monoscript.py [-h] [-D OUTPUT_DIR] [--process-all {NONE,AUTO,INIT}] [--custom-all CUSTOM_ALL] [--additional-all ADDITIONAL_ALL] [--no-organize-imports] [--module-name MODULE_NAME] [--module-version MODULE_VERSION]
                     [--module-description MODULE_DESCRIPTION] [--author AUTHOR] [--license LICENSE] [--project-website PROJECT_WEBSITE] [--requirements REQUIREMENTS] [--requirements-filename REQUIREMENTS_FILENAME]
                     [--additional-headers ADDITIONAL_HEADERS] [--test-scripts-dirname TEST_SCRIPTS_DIRNAME] [--merge-test-scripts] [--no-run-test-scripts]
                     module_path
A Python tool that merges multi-file modules into a single, self-contained script.
positional arguments:
  module_path           Path to the module directory.
options:
  -h, --help            show this help message and exit
  -D OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Output directory for the merged script.
  --process-all {NONE,AUTO,INIT}
                        Strategy for processing __all__ variable.
  --custom-all CUSTOM_ALL
                        Custom __all__ value (comma-separated).
  --additional-all ADDITIONAL_ALL
                        Additional items to add to __all__ (comma-separated).
  --no-organize-imports
                        Disable import organization.
  --module-name MODULE_NAME
                        Name of the output module.
  --module-version MODULE_VERSION
                        Module version.
  --module-description MODULE_DESCRIPTION
                        Module description.
  --author AUTHOR       Author of the module.
  --license LICENSE     Module license.
  --project-website PROJECT_WEBSITE
                        Project website.
  --requirements REQUIREMENTS
                        Module requirements (comma-separated).
  --requirements-filename REQUIREMENTS_FILENAME
                        Module requirements file name.
  --additional-headers ADDITIONAL_HEADERS
                        Additional headers (e.g., 'Key1=Value1,Key2=Value2').
  --test-scripts-dirname TEST_SCRIPTS_DIRNAME
                        Directory name for test scripts.
  --merge-test-scripts  Merge test scripts into the output.
  --no-run-test-scripts
                        Disable running test scripts after merging.
```
---
### Using `monoscript_setup.py`
You can also define the configuration in a `monoscript_setup.py` and run it. Example:
```python
from monoscript import PythonModuleMerger, ProcessAllStrategy
if __name__ == '__main__':
    PythonModuleMerger(
        module_path='./module',
        output_dir='dist',
        # Processing
        process_all_strategy=ProcessAllStrategy.AUTO,
        custom_all=None,
        additional_all=None,
        organize_imports=True,
        # Metadata
        module_version='1.0.0',
        module_description='description',
        author='author',
        license='MIT',
        project_website='http://example.com',
        additional_headers=None,
        # Test Scripts
        test_scripts_dirname='tests',
        merge_test_scripts=False,
        run_test_scripts=True,
    ).merge_files()
```
---
## License
Monoscript is licensed under the MIT License.
---
