import json

def read_config_flag(path: str, key: str) -> bool:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return bool(data.get(key, False))
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return False


def read_config_value(path: str, key: str, default=None):
    """Read an arbitrary config value from a JSON file.

    Returns `default` if the file is missing or invalid.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data.get(key, default)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return default