import copy
from io import BytesIO

from lazurite import util
from .shader_definition import ShaderDefinition
from ..platform import ShaderPlatform
from ..stage import ShaderStage
from .bgfx_shader import BgfxShader


class Variant:
    is_supported: bool
    flags: dict[str, str]
    shaders: list[ShaderDefinition]

    def __init__(self) -> None:
        self.is_supported = False
        self.flags = {}
        self.shaders = []

    def read(self, file: BytesIO):
        self.is_supported = util.read_bool(file)
        flag_count = util.read_ushort(file)
        shader_count = util.read_ushort(file)

        self.flags = {}
        for _ in range(flag_count):
            key = util.read_string(file)
            self.flags[key] = util.read_string(file)

        self.shaders = [ShaderDefinition().read(file) for _ in range(shader_count)]

        return self

    def write(self, file: BytesIO):
        util.write_bool(file, self.is_supported)
        util.write_ushort(file, len(self.flags))
        util.write_ushort(file, len(self.shaders))

        for key in self.flags:
            util.write_string(file, key)
            util.write_string(file, self.flags[key])

        for shader in self.shaders:
            shader.write(file)

        return self

    def serialize_properties(self, index: int):
        obj = {}
        obj["is_supported"] = self.is_supported
        obj["flags"] = self.flags
        obj["shaders"] = [shader.serialize_properties(index) for shader in self.shaders]

        return obj

    def load(self, object: dict, path: str):
        self.is_supported = object.get("is_supported", self.is_supported)
        self.flags = object.get("flags", self.flags)

        if "shaders" in object:
            self.shaders = [
                ShaderDefinition().load(shader, path) for shader in object["shaders"]
            ]
        return self

    def label(self, material_name: str, pass_name: str, variant_index: int):
        for shader in self.shaders:
            shader.label(
                material_name, pass_name, variant_index, self.is_supported, self.flags
            )

        return self

    def get_platforms(self):
        platforms: set[ShaderPlatform] = set()
        for shader in self.shaders:
            platforms.add(shader.platform)

        return platforms

    def get_stages(self):
        stages: set[ShaderStage] = set()
        for shader in self.shaders:
            stages.add(shader.stage)

        return stages

    def merge_variant(self, other: "Variant"):
        for other_shader in other.shaders:
            matching_shader = next(
                (
                    v
                    for v in self.shaders
                    if v.platform == other_shader.platform
                    and v.stage == other_shader.stage
                ),
                None,
            )
            if matching_shader is None:
                self.shaders.append(other_shader)

    def add_platforms(self, platforms: set[ShaderPlatform]):
        current_platforms = self.get_platforms()
        missing_platforms = platforms.difference(current_platforms)
        stages = self.get_stages()

        for platform in missing_platforms:
            for stage in stages:
                shader = next(
                    (x for x in self.shaders if x.stage == stage), ShaderDefinition()
                )
                shader = copy.deepcopy(shader)
                shader.stage = stage
                shader.platform = platform
                shader.bgfx_shader = BgfxShader()
                self.shaders.append(shader)

    def remove_platforms(self, platforms: set[ShaderPlatform]):
        self.shaders = [s for s in self.shaders if s.platform not in platforms]
