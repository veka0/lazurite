import pyjson5, copy, os
from .compiler_type import CompilerType
from lazurite.compiler.macro_define import MacroDefine
from .shader_file_overwrite import ShaderFileOverwrite
from lazurite.material.shader_pass.shader_definition import ShaderPlatform


class MaterialConfig:
    compiler_type: CompilerType
    compiler_options: list[str]
    macro_overwrite_pass: dict[str, list[MacroDefine]]
    macro_overwrite_flags: dict[str, dict[str, list[MacroDefine]]]
    file_overwrite_default: ShaderFileOverwrite
    file_overwrite_pass: dict[str, ShaderFileOverwrite]
    supported_platforms: set[ShaderPlatform]

    def __init__(self) -> None:
        self.compiler_type = CompilerType.SHADERC
        self.compiler_options = []
        self.macro_overwrite_pass = {}
        self.macro_overwrite_flags = {}
        self.file_overwrite_default = ShaderFileOverwrite()
        self.file_overwrite_pass = {}
        self.supported_platforms = set(ShaderPlatform)

    def read_from_json_file(self, file_path: str):
        if not os.path.isfile(file_path):
            return

        with open(file_path) as f:
            mat_json = pyjson5.load(f)
        self.read_json(mat_json)

    def read_json(self, json_data: dict):
        # Compiler config
        compiler_config: dict = json_data.get("compiler", {})

        self.compiler_type = (
            CompilerType.from_name(compiler_config.get("type", ""))
            or self.compiler_type
        )
        self.compiler_options = compiler_config.get("options", self.compiler_options)

        # Macro overwrite
        macro_overwrite: dict = json_data.get("macro_overwrite", {})
        flags: dict[str, dict[str, list[str]]] = macro_overwrite.get("flags", {})
        for _, values in flags.items():
            for key, macros in values.items():
                if type(macros) == str:
                    macros = [macros]
                values[key] = [MacroDefine.from_string(x) for x in macros]
        self.macro_overwrite_flags = flags

        passes: dict = macro_overwrite.get("passes", {})
        for key, value in passes.items():
            if type(value) == str:
                value = [value]
            passes[key] = [MacroDefine.from_string(m) for m in value]

        self.macro_overwrite_pass = passes

        # File overwrite
        file_overwrite: dict = json_data.get("file_overwrite", {})
        self.file_overwrite_default.read_json(file_overwrite.get("default", {}))
        if "passes" in file_overwrite:
            self.file_overwrite_pass = {}
        for key, value in file_overwrite.get("passes", {}).items():
            file_overwrite_pass = copy.copy(self.file_overwrite_default)
            file_overwrite_pass.read_json(value)
            self.file_overwrite_pass[key] = file_overwrite_pass

        # Platforms
        if "supported_platforms" in json_data:
            self.supported_platforms = {
                ShaderPlatform[x] for x in json_data["supported_platforms"]
            }
