import re


def preprocess_shader(shader_code: str):
    """
    Pre-processes plain text shader code to convert it from GLSL to BGFX SC.\n
    Removes built-in `u_` uniforms, replaces `gl_FragColor` and `gl_FragData`,
    replaces attributes and varyings with `$input` and `$output`, removes macros,
    replaces samplers with BGFX AUTOREG macros, adds NUM_THREADS to compute shaders.
    """
    shader_code = re.sub(
        r"^uniform\s+\w+\s+u_[\w[\]]+;\n", "", shader_code, flags=re.MULTILINE
    )

    shader_code = re.sub(r"(\W)bgfx_FragColor(\W)", r"\1gl_FragColor\2", shader_code)
    shader_code = re.sub(r"(\W)bgfx_FragData(\W)", r"\1gl_FragData\2", shader_code)

    shader_code = re.sub(r"^out\s.+?;\n", "", shader_code, flags=re.MULTILINE)

    is_vertex_stage = bool(
        re.search(r"^#define varying out$", shader_code, flags=re.MULTILINE)
    )

    shader_code = re.sub(r"^#define\s.+?\n", "", shader_code, flags=re.MULTILINE)
    shader_code = re.sub(
        r"^#if\s.+?#endif\n", "", shader_code, flags=re.MULTILINE | re.DOTALL
    )
    shader_code = re.sub(r"^#extension\s.+?\n", "", shader_code, flags=re.MULTILINE)

    shader_code = re.sub(
        r"^[\s\w]*?varying\s.+? (\w+);$",
        r"$output \1" if is_vertex_stage else r"$input \1",
        shader_code,
        flags=re.MULTILINE,
    )
    shader_code = re.sub(
        r"^[\s\w]*?attribute\s.+? (\w+);$",
        r"$input \1",
        shader_code,
        flags=re.MULTILINE,
    )

    shader_code = re.sub(r"^#version\s.+?\n", "", shader_code)

    # TODO: Missing some samplers like `uniform lowp sampler2DArray s_WaterSurfaceDepthTextures`
    # (also missing from from bgfx_shader.sh)
    SAMPLERS = [
        (r"lowp sampler2D", r"SAMPLER2D"),
        (r"highp sampler2DMS", r"SAMPLER2DMS"),
        (r"highp sampler3D", r"SAMPLER3D"),
        (r"lowp samplerCube", r"SAMPLERCUBE"),
        (r"highp sampler2DShadow", r"SAMPLER2DSHADOW"),
        (r"highp sampler2D", r"SAMPLER2D_HIGHP"),
        (r"highp samplerCube", r"SAMPLERCUBE_HIGHP"),
        (r"highp sampler2DArray", r"SAMPLER2DARRAY"),
        (r"highp sampler2DMSArray", r"SAMPLER2DMSARRAY"),
        (r"highp samplerCubeArray", r"SAMPLERCUBEARRAY"),
        (r"highp sampler2DArrayShadow", r"SAMPLER2DARRAYSHADOW"),
        (r"highp isampler2D", r"ISAMPLER2D"),
        (r"highp usampler2D", r"USAMPLER2D"),
        (r"highp isampler3D", r"ISAMPLER3D"),
    ]

    for pattern, repl in SAMPLERS:
        pattern = r"^uniform " + pattern + r" (\w+);"
        repl = repl + r"_AUTOREG(\1);"
        shader_code = shader_code = re.sub(
            pattern, repl, shader_code, flags=re.MULTILINE
        )

    shader_code = shader_code = re.sub(
        r"^layout\(std430, .+?\) readonly buffer (\w+) { (\w+) .+? }",
        r"BUFFER_RO_AUTOREG(\1, \2);",
        shader_code,
        flags=re.MULTILINE,
    )
    shader_code = shader_code = re.sub(
        r"^layout\(std430, .+?\) writeonly buffer (\w+) { (\w+) .+? }",
        r"BUFFER_WR_AUTOREG(\1, \2);",
        shader_code,
        flags=re.MULTILINE,
    )
    shader_code = shader_code = re.sub(
        r"^layout\(std430, .+?\) buffer (\w+) { (\w+) .+? }",
        r"BUFFER_RW_AUTOREG(\1, \2)",
        shader_code,
        flags=re.MULTILINE,
    )

    for i, access in enumerate(("readonly ", "writeonly ", "")):
        for prefix in "iu":
            prefix = "u" if prefix == "u" else ""
            access_id = ("RO", "WR", "RW")[i]

            name = f"{prefix.upper()}IMAGE2D_{access_id}_AUTOREG"
            shader_code = re.sub(
                r"^layout\((.+?), .+?\) "
                + access
                + "uniform highp "
                + prefix
                + r"image2D (\w+)",
                name + r"(\2, \1)",
                shader_code,
                flags=re.MULTILINE,
            )

            name = f"{prefix.upper()}IMAGE2D_ARRAY_{access_id}_AUTOREG"
            shader_code = re.sub(
                r"^layout\((.+?), .+?\) "
                + access
                + "uniform highp "
                + prefix
                + r"image2DArray (\w+)",
                name + r"(\2, \1)",
                shader_code,
                flags=re.MULTILINE,
            )

            name = f"{prefix.upper()}IMAGE3D_{access_id}_AUTOREG"
            shader_code = re.sub(
                r"^layout\((.+?), .+?\) "
                + access
                + "uniform highp "
                + prefix
                + r"image3D (\w+)",
                name + r"(\2, \1)",
                shader_code,
                flags=re.MULTILINE,
            )

    shader_code = re.sub(
        r"^layout \(local_size_x = (\d+), local_size_y = (\d+), local_size_z = (\d+)\) in;",
        r"NUM_THREADS(\1, \2, \3)",
        shader_code,
        flags=re.MULTILINE,
    )

    return shader_code


def postprocess_shader(shader_code: str):
    """
    Post-processes plain text shader code to convert it from GLSL to BGFX SC.\n
    Merges `$input` and `$output` declarations together and adds `// Attention!`
    comment to potential array access and matrix multiplication operations.
    """
    shader_code = shader_code.splitlines(keepends=True)

    new_shader = []
    args = []
    line_type = 0  # 0 - none, 1 - input, 2 = output
    line_prefix = ""
    for line in shader_code:
        if line.startswith("$input "):
            current_line_type = 1
            line_prefix = "$input "
        elif line.startswith("$output "):
            current_line_type = 2
            line_prefix = "$output "
        else:
            current_line_type = 0

        if line_type:
            if line_type == current_line_type:
                args.append(line.removeprefix(line_prefix).removesuffix("\n"))
            else:
                new_shader.append(", ".join(args) + "\n")
        if not line_type or line_type != current_line_type:
            if current_line_type:
                args = [line.removesuffix("\n")]
            else:
                new_shader.append(line)

        line_type = current_line_type
    shader_code = new_shader

    for i, line in enumerate(shader_code):
        if ") * (" in line or "][" in line:
            line = line[:-1] + " // Attention!\n"
            shader_code[i] = line

    shader_code = "".join(shader_code)

    return shader_code


def format_function_name(name: str):
    """
    Formats function name such that it can be safely inserted in code and wouldn't conflict with valid GLSL.
    """
    return f"START_NAME|||{name}|||END_NAME"


def strip_comments(code: str):
    """
    Removes single line and multiline comments from GLSL code.
    """
    code = re.sub(r"//.*\n", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"\n\n+", "\n", code)
    return code
