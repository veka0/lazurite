from .diffing import DiffedShader, diff_permutations
from .permutation import (
    ShaderPermutation,
    PermutationBase,
    EncodedUniqufiedPermutations,
)
from .type_aliases import (
    ShaderCode,
    FunctionName,
    ShaderFlags,
    ShaderLine,
    ShaderLineIndex,
)


class EncodedShader:
    """
    This object represents a shader with each unique line of code replaced with a unique number
    """

    main_shader: EncodedUniqufiedPermutations
    functions: dict[FunctionName, EncodedUniqufiedPermutations]
    line_decode_table: list[ShaderLine]

    def __init__(self, permutations: list[ShaderPermutation]):
        self.main_shader = EncodedUniqufiedPermutations()
        self.line_decode_table = []
        self.functions = {}

        uniqufied_functions: dict[FunctionName, dict[ShaderCode, list[ShaderFlags]]] = (
            {}
        )
        uniqufied_main_shader: dict[ShaderCode, list[ShaderFlags]] = {}
        for permutation in permutations:
            # Uniquify main code
            self._insert_flags(uniqufied_main_shader, permutation)

            # Uniquify functions
            for name, func in permutation.functions.items():
                func_code_dict = uniqufied_functions.get(name, None)

                if func_code_dict is None:
                    func_code_dict = {}
                    uniqufied_functions[name] = func_code_dict

                self._insert_flags(func_code_dict, func)

        # Encode main code
        self._encode(uniqufied_main_shader, self.main_shader)

        # Encode functions
        for func_name, table in uniqufied_functions.items():
            encoded_func = EncodedUniqufiedPermutations()
            self._encode(table, encoded_func)
            self.functions[func_name] = encoded_func

    def _insert_flags(
        self, table: dict[ShaderCode, list[ShaderFlags]], permutation: PermutationBase
    ):
        flag_list = table.get(permutation.code, None)

        if flag_list is None:
            flag_list = []
            table[permutation.code] = flag_list

        flag_list.append(permutation.flags)

    def _encode(
        self,
        table: dict[ShaderCode, list[ShaderFlags]],
        shader: EncodedUniqufiedPermutations,
    ):
        for code, flag_list in table.items():
            encoded_shader: list[ShaderLineIndex] = []
            for line in code.splitlines():
                try:
                    line_index = self.line_decode_table.index(line)
                except ValueError:
                    line_index = len(self.line_decode_table)
                    self.line_decode_table.append(line)

                encoded_shader.append(line_index)

            shader.codes.append(encoded_shader)
            shader.flags.append(flag_list)

    def diff(self):
        """
        Diffs encoded shader, which combines together code of all permutations
        """
        diffed_shader = DiffedShader()
        diffed_shader.main_code = diff_permutations(self.main_shader)
        for func_name, func in self.functions.items():
            diffed_shader.functions[func_name] = diff_permutations(func)
        return diffed_shader
