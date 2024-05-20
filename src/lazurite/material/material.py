import pyjson5, json, os
from Crypto.Cipher import AES
from io import BytesIO

from lazurite.decompiler.macro_decompiler import Variant, restore_code
from lazurite.decompiler.varying_decompiler import (
    restore_varying,
    generate_varying_line,
)
from lazurite import util

from .uniform import Uniform
from .buffer import Buffer
from .shader_pass import Pass
from .platform import ShaderPlatform
from .stage import ShaderStage
from .shader_pass.shader_input import ShaderInput
from .encryption import EncryptionType


class Material:
    MAGIC = 168942106
    EXTENSION = ".material.bin"
    COMPILED_MATERIAL_DEFINITION = "RenderDragon.CompiledMaterialDefinition"
    VERSION = 22

    version: int
    name: str
    encryption: EncryptionType
    parent: str
    buffers: list[Buffer]
    uniforms: list[Uniform]
    passes: list[Pass]

    _encryption_key: bytes
    _encryption_nonce: bytes

    def __init__(self):
        self.version = self.VERSION
        self.name = ""
        self.encryption = EncryptionType.NONE
        self.parent = ""
        self.buffers = []
        self.uniforms = []
        self.passes = []

        self._encryption_key = b""
        self._encryption_nonce = b""

    def read(self, file: BytesIO):
        """
        Loads material definition from a binary file-like object.
        """
        self._validate_magic(file)
        self._validate_definition(file)
        self.version = util.read_ulonglong(file)
        self._validate_version()
        self._decrypt_and_read(file)

    def _validate_magic(self, file: BytesIO):
        if self.MAGIC != util.read_ulonglong(file):
            raise Exception("Failed to match file magic")

    def _validate_definition(self, file: BytesIO):
        if util.read_string(file) != self.COMPILED_MATERIAL_DEFINITION:
            raise Exception("Failed to recognize file as material")

    def _validate_version(self):
        if self.version != self.VERSION:
            raise Exception(f"Unsupported material version: {self.version}")

    def _decrypt_and_read(self, file: BytesIO):
        self.encryption = EncryptionType.read(file)

        if self.encryption == EncryptionType.SIMPLE_PASSPHRASE:
            self._encryption_key = util.read_array(file)
            self._encryption_nonce = util.read_array(file)

            cipher = AES.new(
                self._encryption_key,
                AES.MODE_GCM,
                self._get_truncated_nonce(),
            )
            file = BytesIO(cipher.decrypt(util.read_array(file)))

        elif self.encryption == EncryptionType.KEY_PAIR:
            raise Exception("Huh, how did we even get here?")

        self._read_remaining(file)

    def _read_remaining(self, file: BytesIO):
        self.name = util.read_string(file)
        self._read_parent(file)
        self._read_items(file, Buffer, self.buffers, util.read_ubyte)
        self._read_items(file, Uniform, self.uniforms, util.read_ushort)
        self._read_items(file, Pass, self.passes, util.read_ushort)
        self._validate_magic(file)

    def _read_parent(self, file: BytesIO):
        self.parent = util.read_string(file) if util.read_bool(file) else ""

    def _read_items(self, file: BytesIO, item_type, item_list, read_count):
        count = read_count(file)
        item_list[:] = [item_type().read(file) for _ in range(count)]

    def write(self, file: BytesIO):
        """
        Writes material definition into a binary file-like object.
        """
        util.write_ulonglong(file, self.MAGIC)
        util.write_string(file, self.COMPILED_MATERIAL_DEFINITION)
        util.write_ulonglong(file, self.version)

        self.encryption.write(file)
        if self.encryption == EncryptionType.SIMPLE_PASSPHRASE:
            util.write_array(file, self._encryption_key)
            util.write_array(file, self._encryption_nonce)

            data = BytesIO()
            self._write_remaining(data)
            data.seek(0)
            data = data.read()
            cipher = AES.new(
                self._encryption_key,
                AES.MODE_GCM,
                self._get_truncated_nonce(),
            )
            util.write_array(file, cipher.encrypt(data))

        elif self.encryption == EncryptionType.KEY_PAIR:
            raise Exception("Huh, how did we even get here?")

        else:
            self._write_remaining(file)

    def _write_remaining(self, file: BytesIO):
        util.write_string(file, self.name)

        util.write_bool(file, bool(self.parent))
        if self.parent:
            util.write_string(file, self.parent)

        self._write_items(file, self.buffers, util.write_ubyte)
        self._write_items(file, self.uniforms, util.write_ushort)
        self._write_items(file, self.passes, util.write_ushort)

        util.write_ulonglong(file, self.MAGIC)

    def _write_items(self, file: BytesIO, item_list: list, write_count):
        write_count(file, len(item_list))
        for item in item_list:
            item.write(file)

    def _get_truncated_nonce(self):
        return self._encryption_nonce[:12]

    def serialize_properties(self):
        """
        Returns a dictionary with encoded material properties.
        """
        return {
            "version": self.version,
            "name": self.name,
            "parent": self.parent,
            "buffers": [buffer.name for buffer in self.buffers],
            "uniforms": [uniform.name for uniform in self.uniforms],
            "passes": [render_pass.name for render_pass in self.passes],
        }

    def store(self, name: str, path: str = ".", skip_shaders=False):
        """
        Stores material as a file structure.
        """
        material_dir = os.path.join(path, name)
        os.makedirs(material_dir)

        self._store_json(material_dir)
        self._store_items(material_dir, "buffers", self.buffers)
        self._store_items(material_dir, "uniforms", self.uniforms)
        self._store_items(material_dir, "passes", self.passes, skip_shaders)

    def _store_json(self, material_dir):
        json_path = os.path.join(material_dir, "material.json")
        with open(json_path, "w") as f:
            json.dump(self.serialize_properties(), f, indent=4)

    def _store_items(
        self, material_dir: str, subfolder: str, item_list: list, skip_shaders=False
    ):
        if item_list:
            subfolder_dir = os.path.join(material_dir, subfolder)
            os.mkdir(subfolder_dir)

            args = [True] if skip_shaders else []
            for item in item_list:
                item.store(subfolder_dir, *args)

    @classmethod
    def load_bin_file(cls, path: str):
        """
        Creates a material definition from binary file at specified path.
        """
        if os.path.isfile(path):
            material = cls()
            with open(path, "rb") as f:
                material.read(f)
            return material
        else:
            raise Exception(f'Failed to load material at "{path}", it\'s not a file')

    def load_unpacked_material(self, material_path: str):
        """
        Loads unpacked material by merging it with existing material.
        """
        material_json = {}
        material_json_path = os.path.join(material_path, "material.json")
        if os.path.isfile(material_json_path):
            with open(material_json_path) as f:
                material_json: dict = pyjson5.load(f)
        self.version = material_json.get("version", self.VERSION)
        self._validate_version()

        self.name = material_json.get("name", self.name)
        self.parent = material_json.get("parent", self.parent)

        self._load_folder(material_json, material_path, "buffers", self.buffers, Buffer)
        self._load_folder(
            material_json, material_path, "uniforms", self.uniforms, Uniform
        )
        self._load_folder(material_json, material_path, "passes", self.passes, Pass)

    def _load_folder(
        self,
        material_json: dict,
        material_dir: str,
        item_name: str,
        items_list: list,
        constructor,
    ):
        item_names = (
            material_json[item_name]
            if item_name in material_json
            else [item.name for item in items_list]
        )
        folder_path = os.path.join(material_dir, item_name)

        # Read all json files in the folder.
        item_definitions = self._read_item_definitions(folder_path)

        new_items = []
        for name in item_names:
            # Find existing item in the list by name, otherwise create new one.
            item_object = next(
                (item for item in items_list if item.name == name), constructor()
            )
            item_object.name = name
            if name in item_definitions:
                item_object.load(item_definitions[name], folder_path)
            new_items.append(item_object)

        if item_name not in material_json:
            for name, value in item_definitions.items():
                if name in item_names:
                    continue

                new_items.append(constructor().load(value, folder_path))

        items_list[:] = new_items

    def _read_item_definitions(self, folder_path: str):
        item_definitions = {}
        if not os.path.isdir(folder_path):
            return item_definitions
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if not os.path.isfile(file_path) or not file_name.endswith(".json"):
                continue

            with open(file_path) as f:
                definition: dict = pyjson5.load(f)

            if "name" in definition:
                item_definitions[definition["name"]] = definition
            else:
                item_definitions[file_name.removesuffix(".json")] = definition

        return item_definitions

    def label(self):
        """
        Adds comments with information about material into shader code.
        Only for plain text shaders like ESSL, GLSL or Metal.
        """
        for shader_pass in self.passes:
            shader_pass.label(self.name)

    def restore_varying_def(self, search_timeout: float = 10):
        """
        Attempts to restore varying.def.sc file. Works for any platforms.
        """
        permutations: list[Variant] = []
        for p in self.passes:
            per_pass_inputs: dict[
                ShaderPlatform, dict[ShaderStage, list[ShaderInput]]
            ] = {}
            for v in p.variants:
                for s in v.shaders:
                    if s.platform not in per_pass_inputs:
                        per_pass_inputs[s.platform] = {}
                    if s.stage not in per_pass_inputs[s.platform]:
                        per_pass_inputs[s.platform][s.stage] = []
                    input_list = per_pass_inputs[s.platform][s.stage]
                    for i in s.inputs:
                        if i not in input_list:
                            input_list.append(i)

            for platform, stage_dict in per_pass_inputs.items():
                vertex_attributes = []
                fragment_varyings = []
                instance_data = []
                for stage, inputs in stage_dict.items():
                    inputs.sort(key=lambda x: x.name)
                    for i in inputs:
                        is_instance_data, line = generate_varying_line(i, stage)

                        # This shouldn't ever happen.
                        if len([0 for x in inputs if x.name == i.name]) != 1:
                            line += " // ?"

                        if is_instance_data:
                            instance_data.append(line)
                        elif stage == ShaderStage.Vertex:
                            vertex_attributes.append(line)
                        else:
                            fragment_varyings.append(line)
                blocks = []
                if vertex_attributes:
                    blocks.append("\n".join(vertex_attributes))
                if instance_data:
                    blocks.append("\n".join(instance_data))
                if fragment_varyings:
                    blocks.append("\n".join(fragment_varyings))
                if not blocks:
                    continue
                text = "\n\n".join(blocks)
                flags = {"pass": p.name, f"f_platform": platform.name}
                permutations.append(Variant(flags, text))
        if not permutations:
            return ""

        return restore_varying(permutations, search_timeout)

    def restore_shaders(
        self,
        platforms: set[ShaderPlatform],
        stages: set[ShaderStage],
        split_passes=False,
        merge_stages=False,
        process_shaders=False,
        search_timeout: float = 10,
    ) -> list[tuple[ShaderPlatform, ShaderStage, str, str]]:
        """
        Attempts to combine shader permutations into one shader (essl, glsl or metal only only).
        """

        if not self.passes:
            return []

        flag_definition: dict[str, set[str] | list[str]] = {}
        passes: list[str] = []

        restored_shaders: list[tuple[ShaderPlatform, ShaderStage, str, str]] = []

        for p in self.passes:
            passes.append(p.name)
            for key, value in p.default_variant.items():
                if key in flag_definition:
                    flag_definition[key].add(value)
                else:
                    flag_definition[key] = {value}
            for v in p.variants:
                for key, value in v.flags.items():
                    if key in flag_definition:
                        flag_definition[key].add(value)
                    else:
                        flag_definition[key] = {value}
        passes.sort()
        key_list = list(flag_definition.keys())
        key_list.sort()
        flag_definition = {name: flag_definition[name] for name in key_list}
        for name, values in flag_definition.items():
            values = list(values)
            values.sort()
            flag_definition[name] = values

        for platform in platforms:
            shader_definitions: dict[str, dict[ShaderStage, list[Variant]]] = {}
            for shader_pass in self.passes:
                for variant in shader_pass.variants:
                    for shader in variant.shaders:
                        if shader.platform != platform or shader.stage not in stages:
                            continue

                        if shader_pass.name not in shader_definitions:
                            shader_definitions[shader_pass.name] = {}
                        if shader.stage not in shader_definitions[shader_pass.name]:
                            shader_definitions[shader_pass.name][shader.stage] = []
                        code_list = shader_definitions[shader_pass.name][shader.stage]

                        flags = {}
                        if not split_passes:
                            flags["pass"] = shader_pass.name
                        if merge_stages:
                            stage = shader.stage
                            if stage == ShaderStage.Unknown:
                                stage = ShaderStage.Fragment
                            flags["BGFX_SHADER_TYPE_"] = stage.name.upper()
                        for key, value in variant.flags.items():
                            flags["f_" + key] = value

                        code = shader.bgfx_shader.shader_bytes.decode()
                        code_list.append(Variant(flags, code))
            if not shader_definitions:
                continue

            if merge_stages:
                for _, stage_dict in shader_definitions.items():
                    merged_list = []
                    for _, code_list in stage_dict.items():
                        merged_list.extend(code_list)
                    stage_dict.clear()
                    stage_dict[ShaderStage.Fragment] = merged_list
            if not split_passes:
                merged_dict: dict[ShaderStage, list[Variant]] = {}
                for _, stage_dict in shader_definitions.items():
                    for stage, code_list in stage_dict.items():
                        if stage not in merged_dict:
                            merged_dict[stage] = []
                        merged_dict[stage].extend(code_list)
                shader_definitions.clear()
                shader_definitions[self.passes[0].name] = merged_dict

            for shader_pass, stage_dict in shader_definitions.items():
                for stage, code_list in stage_dict.items():
                    macros, code = restore_code(
                        code_list,
                        process_shaders=process_shaders,
                        search_timeout=search_timeout,
                    )
                    # BGFX macros are always defined as either 0 or 1.
                    for stage_name in {"FRAGMENT", "VERTEX", "COMPUTE"}:
                        stage_name = f"BGFX_SHADER_TYPE_{stage_name}"
                        code = (
                            code.replace(f"#ifdef {stage_name}", f"#if {stage_name}")
                            .replace(f"#ifndef {stage_name}", f"#if !{stage_name}")
                            .replace(f"defined({stage_name})", f"{stage_name}")
                        )

                    if flag_definition or passes:
                        comment = "/*\n* Available Macros:"
                        if passes:
                            comment += "\n*\n* Passes:"
                            for pass_name in passes:
                                pass_name = util.generate_pass_name_macro(pass_name)
                                comment += f"\n* - {pass_name}"
                                if pass_name not in macros:
                                    comment += " (not used)"

                        if flag_definition:
                            for flag_name, values in flag_definition.items():
                                comment += f"\n*\n* {flag_name}:"
                                for flag_value in values:
                                    flag = util.generate_flag_name_macro(
                                        flag_name, flag_value, False
                                    )
                                    comment += f"\n* - {flag}"
                                    if flag not in macros:
                                        comment += " (not used)"

                        comment += "\n*/"

                        code = util.insert_header_comment(code, comment)

                        restored_shaders.append((platform, stage, shader_pass, code))

        return restored_shaders

    def sort_variants(self):
        """
        Sorts variants and flags within each variant, useful for diffing.
        """
        for shader_pass in self.passes:
            shader_pass.sort_variants()

    def get_platforms(self):
        """
        Returns available platforms within the material.
        """
        platforms: set[ShaderPlatform] = set()
        for shader_pass in self.passes:
            platforms.update(shader_pass.get_platforms())

        return platforms

    def get_stages(self):
        """
        Returns available stages within the material.
        """
        stages: set[ShaderStage] = set()
        for shader_pass in self.passes:
            stages.update(shader_pass.get_stages())

        return stages

    def merge_variants(self, other: "Material"):
        """
        Merges variants and passes of different materials.
        Useful when creating a single material for multiple platforms.
        """
        for other_pass in other.passes:
            this_pass = next(
                (p for p in self.passes if p.name == other_pass.name), None
            )
            if this_pass is None:
                self.passes.append(other_pass)
            else:
                this_pass.merge_variants(other_pass)

    def get_flag_definitions(self):
        """
        Returns a dict of all possible flag keys and their values.
        """
        definitions: dict[str, set[str]] = {}
        for shader_pass in self.passes:
            pass_defs = shader_pass.get_flag_definitions()
            for key, value in pass_defs.items():
                if key not in definitions:
                    definitions[key] = set()
                definitions[key].update(value)
        return definitions

    def add_platforms(self, platforms: set[ShaderPlatform]):
        for shader_pass in self.passes:
            shader_pass.add_platforms(platforms)

    def remove_platforms(self, platforms: set[ShaderPlatform]):
        for shader_pass in self.passes:
            shader_pass.remove_platforms(platforms)
