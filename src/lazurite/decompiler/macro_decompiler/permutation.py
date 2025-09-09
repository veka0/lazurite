import re

from .processing import format_function_name
from .type_aliases import ShaderCode, FunctionName, ShaderFlags, ShaderLineIndex


class PermutationBase:
    code: ShaderCode
    flags: ShaderFlags

    def __init__(self):
        self.code = ""
        self.flags = {}


class FunctionPermutation(PermutationBase):
    is_struct: bool

    def __init__(self):
        super().__init__()
        self.is_struct = False


class ShaderPermutation(PermutationBase):
    functions: dict[FunctionName, FunctionPermutation]

    def __init__(self):
        super().__init__()
        self.functions = {}

    def extract_functions(self):
        """
        Extracts functions and structs from shader permutation code
        """
        re_func_start = re.compile(
            r"^[\s]*?([^#\s][\w]+)[\s]+([\w]+)[\s]*\(([^;]*?)\)[\s]*{",
            re.DOTALL | re.MULTILINE,
        )
        re_struct_start = re.compile(
            r"^[\s]*?struct[\s]+([\w]+)[\s]*{(.*?)};", re.DOTALL | re.MULTILINE
        )

        func_start = re.search(re_func_start, self.code)
        modified_code = ""

        # Extract functions.
        while func_start:
            groups = func_start.groups()
            args = groups[2].replace("\n", "")
            func_name = f"{groups[0]} {groups[1]}({args})"

            modified_code += self.code[: func_start.start()]

            bracket_balance = 1
            for i in range(func_start.end(), len(self.code)):
                c = self.code[i]
                if c == "{":
                    bracket_balance += 1
                elif c == "}":
                    bracket_balance -= 1

                if bracket_balance == 0:
                    func_content = self.code[func_start.end() : i]
                    self.code = self.code[i + 1 :]
                    break
            if bracket_balance:
                break

            function = FunctionPermutation()
            function.is_struct = False
            function.flags = self.flags
            function.code = func_content
            self.functions[func_name] = function

            modified_code += format_function_name(func_name) + "\n"

            func_start = re.search(re_func_start, self.code)

        self.code = modified_code + self.code

        # Extract structs.
        match: re.Match
        for match in re.finditer(re_struct_start, self.code):
            struct_name, struct_content = match.groups()
            struct_name = "struct " + struct_name

            struct = FunctionPermutation()
            struct.is_struct = True
            struct.flags = self.flags
            struct.code = struct_content
            self.functions[struct_name] = struct

            self.code = self.code.replace(
                match.group(), format_function_name(struct_name) + "\n"
            )


class EncodedUniqufiedPermutations:
    codes: list[list[ShaderLineIndex]]
    flags: list[list[ShaderFlags]]

    def __init__(self):
        self.codes = []
        self.flags = []
