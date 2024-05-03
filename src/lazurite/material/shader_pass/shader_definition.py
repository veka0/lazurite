from io import BytesIO

from lazurite import util
from ..platform import ShaderPlatform
from ..stage import ShaderStage
from .bgfx_shader import BgfxShader
from .shader_input import ShaderInput


class ShaderDefinition:
    stage: ShaderStage
    platform: ShaderPlatform
    inputs: list[ShaderInput]
    hash: int
    bgfx_shader: BgfxShader

    def __init__(self) -> None:
        self.stage = ShaderStage.Unknown
        self.platform = ShaderPlatform.Unknown
        self.inputs = []
        self.hash = 0
        self.bgfx_shader = BgfxShader()

    def read(self, file: BytesIO):
        self.stage = ShaderStage[util.read_string(file)]
        self.platform = ShaderPlatform[util.read_string(file)]

        stage_index = util.read_ubyte(file)
        if self.stage.value != stage_index:
            raise Exception(
                f'Stage name "{self.stage.name}" and index "{stage_index}" do not match! Index "{self.stage.value}" was expected.'
            )

        platform_index = util.read_ubyte(file)
        if self.platform.value != platform_index:
            raise Exception(
                f'Platform name "{self.platform.name}" and index "{platform_index}" do not match! Index "{self.platform.value}" was expected.'
            )

        self.inputs = [ShaderInput().read(file) for _ in range(util.read_ushort(file))]
        self.hash = util.read_ulonglong(file)
        bgfx_shader_bytes = BytesIO(util.read_array(file))
        self.bgfx_shader.read(bgfx_shader_bytes, self.platform, self.stage)

        return self

    def write(self, file: BytesIO):
        util.write_string(file, self.stage.name)
        util.write_string(file, self.platform.name)
        util.write_ubyte(file, self.stage.value)
        util.write_ubyte(file, self.platform.value)

        util.write_ushort(file, len(self.inputs))
        for inp in self.inputs:
            inp.write(file)

        util.write_ulonglong(file, self.hash)
        self.bgfx_shader.write(file, self.platform, self.stage)

        return self

    def get_shader_file_name(self, index: int):
        return f"{index}.{self.platform.name}.{self.stage.name}.{self.platform.file_extension()}"

    def serialize_properties(self, index: int):
        obj = {}
        if index != None:
            obj["file_name"] = self.get_shader_file_name(index)
        obj["stage"] = self.stage.name
        obj["platform"] = self.platform.name
        obj["inputs"] = [
            shaderInput.serialize_properties() for shaderInput in self.inputs
        ]
        obj["hash"] = self.hash
        obj["bgfx_shader"] = self.bgfx_shader.serialize_properties()
        return obj

    def load(self, object: dict, path: str):
        self.stage = ShaderStage[object["stage"]]
        self.platform = ShaderPlatform[object["platform"]]
        self.inputs = [ShaderInput().load(inp) for inp in object["inputs"]]
        self.hash = object["hash"]
        self.bgfx_shader = BgfxShader().load(object, path)
        return self

    def label(
        self,
        material_name: str,
        pass_name: str,
        variant_index: int,
        is_supported: bool,
        flags: dict,
    ):
        if not any(
            self.platform.name.startswith(platform_prefix)
            for platform_prefix in ["ESSL", "GLSL", "Metal"]
        ):
            return self

        comment = (
            "// Shader Information:\n"
            f"// - Name: {material_name}\n"
            f"// - Pass: {pass_name}\n"
            f"// - Platform: {self.platform.name}\n"
            f"// - Stage: {self.stage.name}\n"
            f"// - Variant: {variant_index}\n"
            f"// - Variant Supported: {is_supported}\n"
        )

        if flags:
            comment += "// - Variant Flags: \n"
            comment += "\n".join(
                [f"//    - {flag}: {value}" for flag, value in flags.items()]
            )

        code = self.bgfx_shader.shader_bytes.decode()
        code = util.insert_header_comment(code, comment)
        self.bgfx_shader.shader_bytes = code.encode()

        return self
