import argparse
import time
import os

from concurrent.futures import ProcessPoolExecutor

from lazurite import util
import lazurite.project.project
from lazurite.material import Material
from lazurite.material.stage import ShaderStage
from lazurite.material.platform import ShaderPlatform
from lazurite.material.encryption import EncryptionType
from lazurite.compiler.macro_define import MacroDefine


def list_packed_materials(args) -> list[str]:
    material_files = []
    if len(args.inputs) == 0:
        raise Exception("Material path argument was expected")

    for material_path in args.inputs:
        if not os.path.exists(material_path):
            raise Exception("Invalid path to material or folder")

        if os.path.isfile(material_path):
            material_files.append(material_path)
        else:
            for entry in os.listdir(material_path):
                entry: str
                file_path = os.path.join(material_path, entry)
                if os.path.isfile(file_path) and file_path.endswith(Material.EXTENSION):
                    material_files.append(file_path)

    return material_files


def list_unpacked_materials(args):
    material_folders = []
    for path in args.inputs:
        if not os.path.exists(path):
            raise Exception("Invalid path to material or folder")

        if os.path.isfile(path) and os.path.basename(path) == "material.json":
            material_folders.append(os.path.dirname(path))
        elif os.path.isdir(path) and os.path.isfile(
            os.path.join(path, "material.json")
        ):
            material_folders.append(path)
        elif os.path.isdir(path):
            for child_path in os.listdir(path):
                child_path = os.path.join(path, child_path)
                if os.path.isdir(child_path) and os.path.isfile(
                    os.path.join(child_path, "material.json")
                ):
                    material_folders.append(child_path)

    return material_folders


def unpack(args):
    for file in list_packed_materials(args):
        file_name: str = os.path.basename(file)
        print(file_name)

        material = Material.load_bin_file(file)
        if args.sort_flags:
            material.sort_variants()

        # That should keep the project protected legally.
        skip_shaders = args.skip_shaders
        if material.encryption != EncryptionType.NONE:
            print(
                f"Warning! {material.name} material is encrypted. "
                "This tool cannot be used to obtain decrypted shaders."
            )
            skip_shaders = True

        material.store(
            file_name.removesuffix(Material.EXTENSION), args.output, skip_shaders
        )


def pack(args):
    for file in list_unpacked_materials(args):
        file_name: str = os.path.basename(os.path.abspath(file)) + Material.EXTENSION
        print(file_name)

        material = Material()
        material.load_unpacked_material(file)

        with open(os.path.join(args.output, file_name), "wb") as f:
            material.write(f)


def label(args):
    for file in list_packed_materials(args):
        file_name: str = os.path.basename(file)
        print(file_name)

        material = Material.load_bin_file(file)
        material.label()
        with open(os.path.join(args.output, file_name), "wb") as f:
            material.write(f)


def clear(args):
    for file in list_packed_materials(args):
        file_name: str = os.path.basename(file)
        print(file_name)

        material = Material.load_bin_file(file)

        for shader_pass in material.passes:
            for variant in shader_pass.variants:
                for shader in variant.shaders:
                    shader.bgfx_shader.shader_bytes = bytes()

        material.encryption = EncryptionType.NONE
        with open(os.path.join(args.output, file_name), "wb") as f:
            material.write(f)


def restore_single_material(args, file: str):
    file_name: str = os.path.basename(file)
    print(file_name)
    file_name = file_name.removesuffix(Material.EXTENSION)
    material = Material.load_bin_file(file)

    material.passes.sort(key=lambda x: x.name)
    material.sort_variants()
    varying = material.restore_varying_def(args.timeout)
    if varying:
        with open(os.path.join(args.output, file_name + ".varying.def.sc"), "w") as f:
            f.write(varying)
    else:
        print(
            "Failed to generate varying.def.sc file, no input/output definitions were found in the target material."
        )

    # That should keep the project safe legally.
    if material.encryption != EncryptionType.NONE:
        print(
            f"Warning! {file_name} material is encrypted. "
            "This tool cannot be used to restore decrypted shaders."
        )
        return

    shader_codes = material.restore_shaders(
        {ShaderPlatform.ESSL_310, ShaderPlatform.ESSL_300},
        set(ShaderStage),
        args.split_passes,
        args.merge_stages,
        not args.no_processing,
        args.timeout,
    )
    for platform, stage, shader_pass, code in shader_codes:
        file_name_tokens = [file_name]
        if args.split_passes:
            file_name_tokens.append(shader_pass)
        file_name_tokens.append(platform.name)
        if not args.merge_stages:
            file_name_tokens.append(stage.name)
        file_name_tokens.append(
            platform.file_extension() if args.no_processing else "sc"
        )
        with open(
            os.path.join(args.output, ".".join(file_name_tokens)),
            "w",
        ) as f:
            f.write(code)


def restore(args):
    paths = list_packed_materials(args)

    # Roughly sort tasks by complexity (estimated from file size).
    paths = list(zip(paths, (os.path.getsize(p) for p in paths)))
    paths.sort(key=lambda f: f[1], reverse=True)
    paths = [p[0] for p in paths]

    with ProcessPoolExecutor(max_workers=args.max_workers or None) as executor:
        # Normally, workers will not raise any exceptions during execution
        # but iterating over results will raise them properly.
        for _ in executor.map(restore_single_material, [args] * len(paths), paths):
            pass


def build(args):
    defines = [MacroDefine.from_string(d) for d in args.defines]
    for path in args.inputs:
        print(f'Compiling project "{path}"')
        lazurite.project.project.compile(
            path,
            args.profile,
            args.output,
            args.materials,
            args.exclude,
            defines,
            args.shaderc,
            args.dxc,
            args.shaderc_args,
            args.dxc_args,
            args.max_workers or None,
            not args.skip_validation,
        )


def _format_info(obj: list | dict, depth=0) -> str:
    INDENT = "  "
    SEPARATOR = INDENT + "- "
    txt = "\n" if depth and obj else ""
    if isinstance(obj, list):
        txt += "\n".join(
            (SEPARATOR if depth else "") + _format_info(val, depth + 1) for val in obj
        )
        if obj and depth > 1:
            txt = INDENT + txt.replace("\n", "\n" + INDENT)
    elif isinstance(obj, dict):
        txt += "\n".join(
            (SEPARATOR if depth else "")
            + str(key)
            + (f" ({len(val)})" if isinstance(val, list) else "")
            + ": "
            + _format_info(val, depth + 1)
            for key, val in obj.items()
        )
        if obj and depth > 1:
            txt = INDENT + txt.replace("\n", "\n" + INDENT)
    else:
        return str(obj)

    return txt


def info(args):
    for file in list_packed_materials(args):
        file_name: str = os.path.basename(file)
        material = Material.load_bin_file(file)

        shader_count = 0
        for shader_pass in material.passes:
            for variant in shader_pass.variants:
                shader_count += len(variant.shaders)

        material.buffers.sort(key=lambda x: x.reg1)
        material.sort_variants()
        material.passes.sort(key=lambda x: x.name)
        material.uniforms.sort(key=lambda x: x.name)

        platforms = [p.name for p in material.get_platforms()]
        platforms.sort()
        stages = [p.name for p in material.get_stages()]
        stages.sort()

        info = {
            "Name": material.name,
            "Encryption": material.encryption.name,
            "Parent": material.parent,
            "Total Shaders": shader_count,
            "Platforms": platforms,
            "Stages": stages,
            "Passes": {
                p.name: util.generate_pass_name_macro(p.name) for p in material.passes
            },
            "Flags": {
                key: {v: util.generate_flag_name_macro(key, v) for v in value}
                for key, value in material.get_flag_definitions().items()
            },
            "Buffers": {
                f"{b.precision.name} {b.type.name} {b.name}{' '+ b.texture_format if b.texture_format else ''}": {
                    "Reg1": b.reg1,
                    "Reg2": b.reg2,
                    "Unordered Access": b.unordered_access,
                    "Custom Type Info": (
                        {
                            "Struct": b.custom_type_info.struct,
                            "Size": b.custom_type_info.size,
                        }
                        if b.custom_type_info
                        else ""
                    ),
                }
                for b in material.buffers
            },
            "Uniforms": [
                f"{u.type.name} {u.name}{'['+str(u.count)+']' if u.count > 1 else ''}{(' = [' + ', '.join(str(d) for d in u.default)+']') if u.default else ''}"
                for u in material.uniforms
            ],
        }
        print(f"#### {file_name} ####")
        print(_format_info(info))


def serialize(args):
    for file in list_packed_materials(args):
        file_name: str = os.path.basename(file).removesuffix(Material.EXTENSION)
        print(file_name)

        material = Material.load_bin_file(file)

        material.buffers.sort(key=lambda x: x.name)
        material.uniforms.sort(key=lambda x: x.name)
        material.passes.sort(key=lambda x: x.name)
        material.sort_variants()

        material.store_minimal(file_name, args.output)


def main():
    parser = argparse.ArgumentParser(
        prog="lazurite",
        description="Unofficial shader development tool for Minecraft: Bedrock Edition with RenderDragon graphics engine",
        epilog="For more information, see documentation at https://veka0.github.io/lazurite/",
    )

    commands = {
        "unpack": unpack,
        "pack": pack,
        "label": label,
        "restore": restore,
        "build": build,
        "info": info,
        "clear": clear,
        "serialize": serialize,
        # "project",  # not implemented
        # "config",  # not implemented
    }

    # Common arguments.
    group = parser.add_argument_group("common arguments")
    group.add_argument("command", choices=commands.keys(), help="Command to use")
    group.add_argument("inputs", nargs="*", help="List of inputs")
    group.add_argument("-o", "--output", type=str, default="", help="Output path")
    group.add_argument(
        "--max-workers",
        type=int,
        default=0,
        help="Maximum numbers of cores or processes to use during restore or build commands",
    )

    # Unpack arguments.
    group = parser.add_argument_group("unpack arguments")
    group.add_argument(
        "--sort-flags",
        action="store_true",
        help="Sorts variants and flags alphabeticaly during unpacking",
    )
    group.add_argument(
        "--skip-shaders", action="store_true", help="Don't unpack compiled shaders"
    )

    # Restore arguments.
    group = parser.add_argument_group("restore arguments")
    group.add_argument(
        "--no-processing",
        action="store_true",
        help="Disable additional processing used for converting from restored GLSL to BGFX SC",
    )
    group.add_argument(
        "--timeout",
        type=float,
        default=10,
        help="Maximum time allowed for slow search restoring algorithm, in seconds",
    )
    group.add_argument(
        "--split-passes",
        action="store_true",
        help="Restore separate files for individual passes",
    )
    group.add_argument(
        "--merge-stages",
        action="store_true",
        help="Restore shader stages in a single file",
    )
    # Not implemented.
    # cli_parser.add_argument("--stages", default=["all"], nargs="*")
    # cli_parser.add_argument("--platforms", default=["essl_310"], nargs="*")

    # Build arguments.
    group = parser.add_argument_group("build arguments")
    group.add_argument(
        "-p",
        "--profile",
        type=str,
        nargs="*",
        help="Profiles to use when building projects",
    )
    group.add_argument(
        "-m",
        "--materials",
        type=str,
        nargs="*",
        default=[],
        help="Glob patterns for choosing materials during project compilation.",
    )
    group.add_argument(
        "-e",
        "--exclude",
        type=str,
        nargs="*",
        default=[],
        help="Glob patterns for excluding materials during project compilation.",
    )
    group.add_argument(
        "-d",
        "--defines",
        type=str,
        nargs="*",
        default=[],
        help="Additional defines, passed to shader compiler",
    )
    group.add_argument(
        "--shaderc", type=str, default=None, help="SHADERC compiler command"
    )
    group.add_argument("--dxc", type=str, default=None, help="DXC compiler command")
    group.add_argument(
        "--shaderc-args",
        type=str,
        nargs="*",
        default=[],
        help="Additional SHADERC compiler arguments",
    )
    group.add_argument(
        "--dxc-args",
        type=str,
        nargs="*",
        default=[],
        help="Additional DXC compiler arguments",
    )
    group.add_argument(
        "--skip-validation",
        action="store_true",
        help="Do not validate compiled GLSL and ESSL code.",
    )

    # Execute command.
    args = parser.parse_args()
    current_time = time.perf_counter()

    commands[args.command](args)

    print(f"Completed in {round(time.perf_counter() - current_time, 2)} seconds")
