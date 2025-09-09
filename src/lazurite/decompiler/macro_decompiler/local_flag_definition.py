from .type_aliases import FlagDefinition, FunctionName, FlagName
from .grouped_shader import DiffedShaderWithGroupedLines, CodeLineGroup


class LocalFlagDeinition:
    """
    Separate flag definitions for each context (main code and functions).
    """

    main_shader: FlagDefinition
    functions: dict[FunctionName, FlagDefinition]

    def __init__(self):
        self.main_shader = {}
        self.functions = {}

    @classmethod
    def from_diffed_grouped_shader(cls, shader: DiffedShaderWithGroupedLines):
        obj = cls()

        obj.main_shader = cls._flag_def_from_line_group_list(shader.main_code)
        for func_name, func in shader.functions.items():
            obj.functions[func_name] = cls._flag_def_from_line_group_list(func)

        return obj

    def _flag_def_from_line_group_list(line_list: list[CodeLineGroup]):
        flag_def: FlagDefinition = {}
        for line_group in line_list:
            for flags in line_group.condition:
                for key, value in flags.items():
                    value_list = flag_def.get(key, None)

                    if value_list is None:
                        value_list = []
                        flag_def[key] = value_list

                    if value not in value_list:
                        value_list.append(value)

        return flag_def

    def filter_and_bias_flags(self):
        """
        Removes flags that are always set and biases boolean flags (On/Off, Enabled/Disabled) in expression search towards enabling and against disabling
        """
        definitions: list[FlagDefinition] = list(self.functions.values())
        definitions.append(self.main_shader)

        for flag_def in definitions:
            keys_to_remove: list[FlagName] = []
            for flag_name, flag_values in flag_def.items():
                if len(flag_values) <= 1:
                    keys_to_remove.append(flag_name)
                    continue
                # Bias against disabling
                for i in ("Off", "Disabled"):
                    if i in flag_values:
                        flag_values.remove(i)
                        flag_values.append(i)
                # Bias towards enabling
                for i in ("On", "Enabled"):
                    if i in flag_values:
                        flag_values.remove(i)
                        flag_values.insert(0, i)

            for key in keys_to_remove:
                flag_def.pop(key)
