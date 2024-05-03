from lazurite import util
from ..platform import ShaderPlatform
from ..stage import ShaderStage
from io import BytesIO
import struct, os


class BgfxUniform:
    name: str
    type_bits: int
    count: int
    reg_index: int
    reg_count: int

    def read(self, file: BytesIO):
        self.name = file.read(util.read_ubyte(file)).decode()
        self.type_bits = util.read_ubyte(file)
        self.count = util.read_ubyte(file)
        self.reg_index = util.read_ushort(file)
        self.reg_count = util.read_ushort(file)

        return self

    def write(self, file: BytesIO):
        util.write_ubyte(file, len(self.name))
        file.write(self.name.encode())
        util.write_ubyte(file, self.type_bits)
        util.write_ubyte(file, self.count)
        util.write_ushort(file, self.reg_index)
        util.write_ushort(file, self.reg_count)
        return self

    def serialize_properties(self):
        obj = {}
        obj["name"] = self.name
        obj["type_bits"] = self.type_bits
        obj["count"] = self.count
        obj["reg_index"] = self.reg_index
        obj["reg_count"] = self.reg_count
        return obj

    def load(self, object: dict):
        self.name = object["name"]
        self.type_bits = object["type_bits"]
        self.count = object["count"]
        self.reg_index = object["reg_index"]
        self.reg_count = object["reg_count"]
        return self


class BgfxShader:
    hash: int
    uniforms: list[BgfxUniform]
    group_size: list[int]
    shader_bytes: bytes
    attributes: list[int]  # Array of attribute IDs
    size: int

    def __init__(self) -> None:
        self.hash = 0
        self.uniforms = []
        self.group_size = []
        self.shader_bytes = b""
        self.attributes = []
        self.size = 0

    def read(self, file: BytesIO, platform: ShaderPlatform, stage: ShaderStage):
        header = file.read(3).decode()
        if not header in ["VSH", "FSH", "CSH"]:
            raise Exception(f'Unrecognized BGFX shader bin header "{header}"')

        version = util.read_ubyte(file)
        if not (version == 5 or version == 3 and header == "CSH"):
            raise Exception(f"Unsupported BGFX shader bin version: {version}")

        self.hash = util.read_ulong(file)
        self.uniforms = [
            BgfxUniform().read(file) for _ in range(util.read_ushort(file))
        ]

        if platform == ShaderPlatform.Metal and stage == ShaderStage.Compute:
            self.group_size = [
                util.read_ushort(file),
                util.read_ushort(file),
                util.read_ushort(file),
            ]
        else:
            self.group_size = []

        self.shader_bytes = file.read(util.read_ulong(file))
        util.read_ubyte(file)  # Padding (always 0)

        attribute_count = file.read(1)
        if len(attribute_count) != 0:
            self.attributes = [
                util.read_ushort(file)
                for _ in range(struct.unpack("<B", attribute_count)[0])
            ]
            self.size = util.read_ushort(file)
        else:
            self.attributes = []
            self.size = -1

        return self

    def write(self, file: BytesIO, platform: ShaderPlatform, stage: ShaderStage):
        bgfx_file = BytesIO()

        header = "FSH"
        version = 5
        if stage == ShaderStage.Vertex:
            header = "VSH"
        elif stage == ShaderStage.Compute:
            header = "CSH"
            version = 3

        bgfx_file.write(header.encode())
        util.write_ubyte(bgfx_file, version)

        util.write_ulong(bgfx_file, self.hash)

        util.write_ushort(bgfx_file, len(self.uniforms))
        for uniform in self.uniforms:
            uniform.write(bgfx_file)

        if platform == ShaderPlatform.Metal and stage == ShaderStage.Compute:
            for i in range(3):
                util.write_ushort(bgfx_file, self.group_size[i])

        util.write_ulong(bgfx_file, len(self.shader_bytes))
        bgfx_file.write(self.shader_bytes)

        util.write_ubyte(bgfx_file, 0)  # Padding

        if self.size != -1:
            util.write_ubyte(bgfx_file, len(self.attributes))
            for attribute in self.attributes:
                util.write_ushort(bgfx_file, attribute)

            util.write_ushort(bgfx_file, self.size)

        bgfx_file.seek(0)
        util.write_array(file, bgfx_file.read())
        return self

    def serialize_properties(self):
        obj = {}
        obj["hash"] = self.hash
        obj["uniforms"] = [uniform.serialize_properties() for uniform in self.uniforms]
        obj["group_size"] = self.group_size
        obj["attributes"] = self.attributes
        obj["size"] = self.size
        return obj

    def load(self, object: dict, path: str):
        bgfx_obj = object["bgfx_shader"]
        self.hash = bgfx_obj["hash"]
        self.uniforms = [
            BgfxUniform().load(uniform) for uniform in bgfx_obj["uniforms"]
        ]
        self.group_size = bgfx_obj["group_size"]
        self.attributes = bgfx_obj["attributes"]
        self.size = bgfx_obj["size"]

        with open(os.path.join(path, object["file_name"]), "rb") as f:
            self.shader_bytes = f.read()

        return self
