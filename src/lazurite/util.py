from io import BytesIO
from functools import cache
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


def generate_shader_header_comment(comment_data: dict[str, list[str]]):
    lines = ["/*"]

    for label, values in comment_data.items():
        lines.append(f"* {label}:")
        for value in values:
            lines.append(f"* - {value}")
        lines.append("*")

    if lines[-1] == "*":
        lines.pop()
    lines.append("*/")

    return "\n".join(lines)


def hash_murmur2a(data: bytes, seed=0) -> int:
    """
    MurMur2A hash. Used by the game to calculate output binding signature.
    """
    M = 0x5BD1E995
    R = 24
    MASK_32 = 2**32 - 1

    def mmix(h, k):
        k = (k * M) & MASK_32
        k ^= k >> R
        k = (k * M) & MASK_32
        h = (h * M) & MASK_32
        h ^= k

        return h, k

    l = len(data)

    h = seed

    for i in range(0, (len(data) // 4) * 4, 4):
        k = int.from_bytes(data[i : i + 4], "little")
        h, k = mmix(h, k)

    t = 0
    for i in range(len(data) % 4, 0, -1):
        t ^= data[i + (len(data) // 4) * 4 - 1] << ((i - 1) * 8)

    h, t = mmix(h, t)
    h, l = mmix(h, l)

    h ^= h >> 13
    h = (h * M) & MASK_32
    h ^= h >> 15

    return h


def hash_fnv1_64(string: str):
    """
    64bit fnv1 hash.
    """
    OFFSET = 0xCBF29CE484222325
    PRIME = 0x100000001B3
    MASK_64 = 2**64 - 1

    hash = OFFSET
    for b in string.encode():
        hash = (hash * PRIME) & MASK_64
        hash ^= b

    return hash


def get_output_binding_signature(
    named_fragment_outputs: list[str], sort_intermediate_hashes=True
) -> int:
    """
    Returns output binding signature for a gven list of named framebuffer outputs.

    `sort_intermediate_hashes` parameter makes it such that the exact order of outputs in the list doesn't matter.
    It is set to true by default, as the game appears to apply this sorting, when calculating binding signatures.

    Example usage:
    ```
    get_output_binding_signature([]) # -> 0
    get_output_binding_signature(['Color0']) # -> 1268872610
    get_output_binding_signature(['Color1']) # -> 1444265990
    get_output_binding_signature(['Color0', 'Color1']) # -> 102126840
    get_output_binding_signature(['Color0', 'Color1', 'Color2']) # -> 3853911848
    ```
    """
    hashes = [hash_fnv1_64(x) for x in named_fragment_outputs]

    if sort_intermediate_hashes:
        hashes.sort()

    data = b""
    for hash in hashes:
        data += hash.to_bytes(8)[::-1]

    return hash_murmur2a(data)


@cache
def _reconstruct_fragment_outputs(
    output_binding_signature: int,
) -> list[str] | None:
    if output_binding_signature == 0:
        return []

    INDICES_TO_CHECK = 8
    MAX_FRAGMENT_OUTPUTS = 4  # How many outputs to check

    for binding_count in range(1, MAX_FRAGMENT_OUTPUTS):
        for i in range(INDICES_TO_CHECK**binding_count):
            data = b""

            packed_indices = i
            for _ in range(binding_count):
                index = packed_indices % INDICES_TO_CHECK
                data += hash_fnv1_64(f"Color{index}").to_bytes(8)[::-1]
                packed_indices //= INDICES_TO_CHECK

            if hash_murmur2a(data) == output_binding_signature:
                named_outputs = []

                packed_indices = i
                for _ in range(binding_count):
                    index = packed_indices % INDICES_TO_CHECK
                    named_outputs.append(f"Color{index}")
                    packed_indices //= INDICES_TO_CHECK

                return named_outputs

    return None


def reconstruct_fragment_outputs(
    output_binding_signature: int,
) -> list[str] | None:
    """
    Attempts to reconstruct a list of named framebuffer outputs, based on the provided output binding signature. Returns `None` if it fails to find the right combination.

    It works by checking all combinations of names, up to a certain limit, until one of them produces the right hash.
    This function is cached, so once a solution for a given signature is found, it will be reused for subsequent function calls with the same inputs.

    Example usage:
    ```
    reconstruct_fragment_outputs(0) # -> []
    reconstruct_fragment_outputs(1268872610) # -> ['Color0']
    reconstruct_fragment_outputs(1444265990) # -> ['Color1']
    reconstruct_fragment_outputs(102126840) # -> ['Color0', 'Color1']
    reconstruct_fragment_outputs(3853911848) # -> ['Color2', 'Color0', 'Color1']
    reconstruct_fragment_outputs(12345) # -> None
    ```
    """
    output = _reconstruct_fragment_outputs(output_binding_signature)

    if isinstance(output, list):
        output = output.copy()

    return output
