from io import BytesIO
import struct
import re

from lazurite.material.platform import ShaderPlatform


# Reading binary files.
def read_ulonglong(f: BytesIO) -> int:
    """8 bytes"""
    return struct.unpack("<Q", f.read(8))[0]


def read_ulong(f: BytesIO) -> int:
    """4 bytes"""
    return struct.unpack("<L", f.read(4))[0]


def read_bool(f: BytesIO) -> bool:
    """1 byte"""
    return struct.unpack("<?", f.read(1))[0]


def read_ubyte(f: BytesIO) -> int:
    """1 byte"""
    return struct.unpack("<B", f.read(1))[0]


def read_ushort(f: BytesIO) -> int:
    """2 bytes"""
    return struct.unpack("<H", f.read(2))[0]


def read_array(f: BytesIO) -> bytes:
    """4 bytes length, N-byte array"""
    return f.read(struct.unpack("<I", f.read(4))[0])


def read_string(f: BytesIO) -> str:
    """4 bytes length, N-byte string"""
    return read_array(f).decode()


# Writing binary files.
def write_ulonglong(f: BytesIO, val: int):
    """8 bytes"""
    f.write(struct.pack("<Q", val))


def write_ulong(f: BytesIO, val: int):
    """4 bytes"""
    f.write(struct.pack("<L", val))


def write_bool(f: BytesIO, val: bool):
    """1 byte"""
    f.write(struct.pack("<?", val))


def write_ubyte(f: BytesIO, val: int):
    """1 byte"""
    f.write(struct.pack("<B", val))


def write_ushort(f: BytesIO, val: int):
    """2 bytes"""
    f.write(struct.pack("<H", val))


def write_array(f: BytesIO, val: bytes):
    """4 bytes length, N-byte array"""
    f.write(struct.pack("<I", len(val)))
    f.write(val)


def write_string(f: BytesIO, val: str):
    """4 bytes length, N-byte string"""
    write_array(f, val.encode())


def format_definition_name(name: str):
    # aA -> a_A
    name = re.sub(r"([a-z]+)([A-Z])", r"\1_\2", name)
    # AAa -> A_Aa
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # X00 -> X_00
    # name = re.sub(r"([a-zA-Z])(\d+)", r"\1_\2", name)
    # 00X -> 00_X
    name = re.sub(r"(\d+)([a-zA-Z])", r"\1_\2", name)
    return name.upper()


def generate_flag_name_macro(key: str, value: str, is_bool: bool = False):
    if is_bool:
        return format_definition_name(key)
    else:
        return format_definition_name(key + "__" + value)


def generate_pass_name_macro(name: str):
    name = format_definition_name(name)
    if name.endswith("_PASS"):
        return name
    return name + "_PASS"


def insert_header_comment(code: str, comment: str):
    if code.startswith("#version"):
        return code.replace("\n", "\n\n" + comment + "\n\n", 1)
    else:
        return comment + "\n\n" + code


def insert_version_directive(code: str, platform: ShaderPlatform):
    if not re.search(r"^\s*#\s*version\s+", code, re.MULTILINE):
        version_string = platform.name[-3:]
        if platform in (ShaderPlatform.ESSL_300, ShaderPlatform.ESSL_310):
            version_string += " es"
        code = f"#version {version_string}\n{code}"
    return code
