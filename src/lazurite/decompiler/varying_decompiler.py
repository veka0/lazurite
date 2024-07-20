import re


from .macro_decompiler import restore_code, Variant
from lazurite import util
from lazurite.material.stage import ShaderStage
from lazurite.material.platform import ShaderPlatform
from lazurite.material.shader_pass.shader_input import (
    Interpolation,
    Precision,
    ShaderInput,
)


def generate_varying_line(shader_input: ShaderInput, stage: ShaderStage):
    """
    Creates a text line from varying.def.sc for a specific shader input and stage.
    """
    line = ""
    is_instance_data = False

    if shader_input.precision != Precision.none:
        line += shader_input.precision.name + " "
    if shader_input.interpolation != Interpolation.none:
        line += shader_input.interpolation.name + " "
    line += shader_input.type.name + " "
    name = shader_input.name
    if name.startswith("instanceData"):
        name = f"i_data{int(name.removeprefix('instanceData'))+1}"
        is_instance_data = True
    elif stage == ShaderStage.Vertex:
        name = "a_" + shader_input.semantic.get_variable_name()
    else:
        name = "v_" + name
    line += f"{name} : {shader_input.semantic.get_name()};"

    return is_instance_data, line


def _postprocess_varying(code: str):
    """
    Formats generated varying.def code and corrects platform macros.
    """
    a_pattern = re.compile(r"^(.+? )(a_\w+)([\s]+: [\w]+;)", re.MULTILINE)
    i_pattern = re.compile(r"^(.+? )(i_\w+)([\s]+: [\w]+;)", re.MULTILINE)
    v_pattern = re.compile(r"^(.+? )(v_\w+)([\s]+: [\w]+;)", re.MULTILINE)

    for pattern in [a_pattern, i_pattern, v_pattern]:
        matches: list[re.Match] = re.findall(pattern, code)
        if not matches:
            continue
        max_type_len = max((len(x[0]) for x in matches))
        max_name_len = max((len(x[1]) for x in matches))

        def replacement(m: re.Match):
            g = m.groups()
            txt = g[0] + (max_type_len - len(g[0])) * " "
            txt += g[1] + (max_name_len - len(g[1])) * " "
            return txt + g[2]

        code = re.sub(pattern, replacement, code)

    for platform in ShaderPlatform:
        lang = "UNKNOWN"
        version = 1
        if platform.name.startswith("Direct3D_"):
            lang = "HLSL"
            if platform == ShaderPlatform.Direct3D_SM40:
                version = 400
            elif platform.name.startswith("Direct3D_SM"):
                version = 500
        elif platform.name.startswith("GLSL_") or platform.name.startswith("ESSL_"):
            lang = "GLSL"
            version = int(platform.name[-3:])
        elif platform == ShaderPlatform.Vulkan:
            lang = "SPIRV"
        elif platform == ShaderPlatform.Nvn:
            pass  # Don't know what should be used here.
        else:
            lang = platform.name.upper()

        lang = f"BGFX_SHADER_LANGUAGE_{lang}"
        macro = util.generate_flag_name_macro("platform", platform.name)
        code = (
            code.replace(f"defined({macro})", f"({lang} == {version})")
            .replace(f"#ifdef {macro}", f"#if {lang} == {version}")
            .replace(f"#ifndef {macro}", f"#if {lang} != {version}")
        )
    return code


def restore_varying(permutations: list[Variant], search_timeout: float = 10):
    _, code = restore_code(permutations, False, search_timeout=search_timeout)

    return _postprocess_varying(code)
