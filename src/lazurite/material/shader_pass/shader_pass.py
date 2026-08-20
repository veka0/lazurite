from io import BytesIO
import os, json

from lazurite import util
from .variant import Variant
from ..platform import ShaderPlatform
from ..stage import ShaderStage
from .blend_mode import BlendMode
from .supported_platforms import SupportedPlatforms
from .shader_input import ShaderInput


class Pass:
    name: str
    supported_platforms: SupportedPlatforms
    fallback_pass: str
    default_blend_mode: BlendMode
    flag_domain: dict[str, list[str]]
    output_binding_signature: int
    variants: list[Variant]

    def __init__(self):
        self.name = ""
        self.supported_platforms = SupportedPlatforms()
        self.fallback_pass = ""
        self.default_blend_mode = BlendMode.Unspecified
        self.flag_domain = {}
        self.output_binding_signature = 0
        self.variants = []

    def read(self, file: BytesIO, version: int):
        self.name = util.read_string(file)
        self.supported_platforms = SupportedPlatforms().parse_bit_string(
            util.read_string(file), version
        )
        self.fallback_pass = util.read_string(
            file
        )  # (empty string) Fallback DoCheckerboarding DepthOnlyFallback

        if util.read_bool(file):  # Has default blend mode
            self.default_blend_mode = BlendMode[util.read_ushort(file)]

        self.flag_domain = {}
        if version >= 26:
            for _ in range(util.read_ushort(file)):
                key = util.read_string(file)
                values = [util.read_string(file) for _ in range(util.read_ushort(file))]
                self.flag_domain[key] = values
        else:
            # Read default variant as flag domain with 1 value for each flag,
            # since the first value of each flag in flag domain corresponds to the variant that the game uses as default
            for _ in range(util.read_ushort(file)):
                key = util.read_string(file)
                self.flag_domain[key] = [util.read_string(file)]

        if version >= 23:
            self.output_binding_signature = util.read_ulong(file)

        self.variants = [
            Variant().read(file, version) for _ in range(util.read_ushort(file))
        ]

        return self

    def write(self, file: BytesIO, version: int):
        util.write_string(file, self.name)
        util.write_string(file, self.supported_platforms.get_bit_string(version))
        util.write_string(file, self.fallback_pass)

        util.write_bool(file, self.default_blend_mode != BlendMode.Unspecified)
        if self.default_blend_mode != BlendMode.Unspecified:
            util.write_ushort(file, self.default_blend_mode.value)

        if version >= 26:
            util.write_ushort(file, len(self.flag_domain))
            for key, values in self.flag_domain.items():
                util.write_string(file, key)
                util.write_ushort(file, len(values))
                for value in values:
                    util.write_string(file, value)
        else:
            util.write_ushort(file, len(self.flag_domain))
            for key in self.flag_domain:
                util.write_string(file, key)
                util.write_string(file, self.flag_domain[key][0])

        if version >= 23:
            util.write_ulong(file, self.output_binding_signature)

        util.write_ushort(file, len(self.variants))
        for variant in self.variants:
            variant.write(file, version)
        return self

    def serialize_properties(self, version: int):
        obj = {}
        obj["name"] = self.name
        obj["supported_platforms"] = self.supported_platforms.serialize(version)
        obj["fallback_pass"] = self.fallback_pass
        obj["default_blend_mode"] = (
            self.default_blend_mode.name
            if self.default_blend_mode != BlendMode.Unspecified
            else ""
        )
        obj["flag_domain"] = self.flag_domain

        obj["output_binding_signature"] = self.output_binding_signature

        obj["variants"] = []
        for i, variant in enumerate(self.variants):
            obj["variants"].append(variant.serialize_properties(i))

        return obj

    def serialize_minimal(
        self,
        flag_definitions: dict[str, list[str]],
        input_definitions: list[ShaderInput],
        version: int,
    ):
        obj = [
            self.name,
            self.supported_platforms.get_bit_string(version),
            self.fallback_pass,
            (
                self.default_blend_mode.value
                if self.default_blend_mode != BlendMode.Unspecified
                else ""
            ),
            self.flag_domain,
            self.output_binding_signature,
        ]

        variants = []
        for variant in self.variants:
            variants.append(
                variant.serialize_minimal(flag_definitions, input_definitions)
            )
        obj.append(variants)

        return obj

    def load_minimal(
        self,
        object: dict,
        flag_definitions: dict[str, list[str]],
        input_definitions: list[ShaderInput],
        version: int,
    ):
        self.name = object[0]
        self.supported_platforms = SupportedPlatforms().parse_bit_string(
            object[1], version
        )
        self.fallback_pass = object[2]
        mode = object[3]
        self.default_blend_mode = BlendMode(mode) if mode else BlendMode.Unspecified

        self.flag_domain = object[4]

        self.output_binding_signature = object[5]
        self.variants = [
            Variant().load_minimal(variant, flag_definitions, input_definitions)
            for variant in object[6]
        ]
        return self

    def store(self, version: int, path: str = ".", skip_shaders=False):
        pass_dir = os.path.join(path, self.name)

        with open(os.path.join(path, f"{self.name}.json"), "w") as f:
            json.dump(self.serialize_properties(version), f, indent=4)

        if skip_shaders:
            return self

        os.mkdir(pass_dir)

        for i in range(len(self.variants)):
            for shader in self.variants[i].shaders:
                with open(
                    os.path.join(pass_dir, shader.get_shader_file_name(i)), "wb"
                ) as f:
                    f.write(shader.bgfx_shader.shader_bytes)

        return self

    def load(self, object: dict, path: str):
        self.name = object.get("name", self.name)
        self.supported_platforms.load(object.get("supported_platforms", {}))
        self.fallback_pass = object.get("fallback_pass", self.fallback_pass)
        mode = object.get("default_blend_mode", None)
        if mode != None:
            self.default_blend_mode = BlendMode[mode] if mode else BlendMode.Unspecified
        self.flag_domain = object.get("flag_domain", self.flag_domain)

        if "variants" in object:
            self.variants = [
                Variant().load(variant, os.path.join(path, self.name))
                for variant in object["variants"]
            ]
        self.output_binding_signature = object.get(
            "output_binding_signature", self.output_binding_signature
        )
        return self

    def label(self, material_name: str):
        for variant_index, variant in enumerate(self.variants):
            variant.label(material_name, self.name, variant_index)

        return self

    def sort_variants(self):
        self.flag_domain = dict(sorted(self.flag_domain.items()))

        for variant in self.variants:
            variant.flags = dict(sorted(variant.flags.items()))

        self.variants.sort(key=lambda x: str(x.flags))

    def get_platforms(self):
        platforms: set[ShaderPlatform] = set()
        for variant in self.variants:
            platforms.update(variant.get_platforms())

        return platforms

    def get_stages(self):
        stages: set[ShaderStage] = set()
        for variant in self.variants:
            stages.update(variant.get_stages())

        return stages

    def merge_variants(self, other: "Pass"):
        for other_variant in other.variants:
            matching_variant = next(
                (v for v in self.variants if v.flags == other_variant.flags), None
            )
            if matching_variant is None:
                self.variants.append(other_variant)
            else:
                matching_variant.merge_variant(other_variant)

    def get_flag_definitions(self):
        """
        Returns a dict of all possible flag keys and their values.
        """
        definitions = {key: {values[0]} for key, values in self.flag_domain.items()}

        for variant in self.variants:
            for key, value in variant.flags.items():
                if key not in definitions:
                    definitions[key] = set()
                definitions[key].add(value)
        return definitions

    def add_platforms(self, platforms: set[ShaderPlatform]):
        for variant in self.variants:
            variant.add_platforms(platforms)

    def remove_platforms(self, platforms: set[ShaderPlatform]):
        for variant in self.variants:
            variant.remove_platforms(platforms)
