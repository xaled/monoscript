COLORS = {
    "success": "\033[92m",  # Green
    "info": "\033[94m",  # Blue
    "warning": "\033[93m",  # Yellow
    "error": "\033[91m",  # Red
    "reset": "\033[0m",  # Reset to default color
}


def _print_colored(color, *args, **kwargs):
    """Prints a message with the specified color."""
    print(f"{COLORS[color]}", *args, f"{COLORS['reset']}", **kwargs)


def success(*args, sep=" ", end="\n", file=None, **kwargs):
    """Prints a success message (green)."""
    _print_colored("success", *args, sep=sep, end=end, file=file, **kwargs)


def info(*args, sep=" ", end="\n", file=None, **kwargs):
    """Prints an info message (blue)."""
    _print_colored("info", *args, sep=sep, end=end, file=file, **kwargs)


def warning(*args, sep=" ", end="\n", file=None, **kwargs):
    """Prints a warning message (yellow)."""
    _print_colored("warning", *args, sep=sep, end=end, file=file, **kwargs)


def error(*args, sep=" ", end="\n", file=None, **kwargs):
    """Prints an error message (red)."""
    _print_colored("error", *args, sep=sep, end=end, file=file, **kwargs)
