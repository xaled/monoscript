import argparse
from .merger import PythonModuleMerger, ProcessAllStrategy


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="A Python tool that merges multi-file modules into a single, self-contained script.")

    parser.add_argument("module_path", help="Path to the module directory.")
    parser.add_argument("-D", "--output_dir", default="dist", help="Output directory for the merged script.")
    parser.add_argument("--process-all", choices=["NONE", "AUTO", "INIT"], default="AUTO",
                        help="Strategy for processing __all__ variable.")
    parser.add_argument("--custom-all", help="Custom __all__ value (comma-separated).")
    parser.add_argument("--additional-all", help="Additional items to add to __all__ (comma-separated).")
    parser.add_argument("--no-organize-imports", action="store_false", dest="organize_imports",
                        help="Disable import organization.")
    parser.add_argument("--module-name", help="Name of the output module.")

    # Metadata arguments
    parser.add_argument("--module-version", default="", help="Module version.")
    parser.add_argument("--module-description", default="", help="Module description.")
    parser.add_argument("--author", default="", help="Author of the module.")
    parser.add_argument("--license", default="", help="Module license.")
    parser.add_argument("--project-website", help="Project website.")
    parser.add_argument("--additional-headers", help="Additional headers (e.g., 'Key1=Value1,Key2=Value2').")

    # Test script arguments
    parser.add_argument("--test-scripts-dirname", default="tests", help="Directory name for test scripts.")
    parser.add_argument("--merge-test-scripts", action="store_true", help="Merge test scripts into the output.")
    parser.add_argument("--no-run-test-scripts", action="store_false", dest="run_test_scripts",
                        help="Disable running test scripts after merging.")

    args = parser.parse_args(args=argv)

    process_all_strategy = ProcessAllStrategy[args.process_all]

    additional_headers = {}
    if args.additional_headers:
        for item in args.additional_headers.split(','):
            key, value = item.split("=")
            additional_headers[key] = value

    merger = PythonModuleMerger(
        module_path=args.module_path,
        output_dir=args.output_dir,
        process_all_strategy=process_all_strategy,
        custom_all=args.custom_all.split(',') if args.custom_all else None,  # Split comma-separated values
        additional_all=args.additional_all.split(',') if args.additional_all else None,
        organize_imports=args.organize_imports,
        module_name=args.module_name,
        module_version=args.module_version,
        module_description=args.module_description,
        author=args.author,
        license=args.license,
        project_website=args.project_website,
        additional_headers=additional_headers,
        test_scripts_dirname=args.test_scripts_dirname,
        merge_test_scripts=args.merge_test_scripts,
        run_test_scripts=None if args.run_test_scripts else False,
    )

    merger.merge_files()
    return merger


if __name__ == "__main__":
    main()
