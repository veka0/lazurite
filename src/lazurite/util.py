from io import BytesIO
import struct
import re


# Reading binary files.
def read_ulonglong(f: BytesIO) -> int:
    return struct.unpack("<Q", f.read(8))[0]


def read_ulong(f: BytesIO) -> int:
    return struct.unpack("<L", f.read(4))[0]


def read_bool(f: BytesIO) -> bool:
    return struct.unpack("<?", f.read(1))[0]


def read_ubyte(f: BytesIO) -> int:
    return struct.unpack("<B", f.read(1))[0]


def read_ushort(f: BytesIO) -> int:
    return struct.unpack("<H", f.read(2))[0]


def read_array(f: BytesIO) -> bytes:
    return f.read(struct.unpack("<I", f.read(4))[0])


def read_string(f: BytesIO) -> str:
    return read_array(f).decode()


# writing binary files.
def write_ulonglong(f: BytesIO, val: int):
    f.write(struct.pack("<Q", val))


def write_ulong(f: BytesIO, val: int):
    f.write(struct.pack("<L", val))


def write_bool(f: BytesIO, val: bool):
    f.write(struct.pack("<?", val))


def write_ubyte(f: BytesIO, val: int):
    f.write(struct.pack("<B", val))


def write_ushort(f: BytesIO, val: int):
    f.write(struct.pack("<H", val))


def write_array(f: BytesIO, val: bytes):
    f.write(struct.pack("<I", len(val)))
    f.write(val)


def write_string(f: BytesIO, val: str):
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
