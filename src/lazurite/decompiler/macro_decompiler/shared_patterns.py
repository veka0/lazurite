import re

FUNCTION_NAME_PATTERN = re.compile(r"(?<!\w)func_\w+")
VARIABLE_NAME_PATTERN = re.compile(r"(?<!\w)_\d+")
