import os, pyjson5, pcpp, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

# Try importing optional dependency.
try:
    import moderngl
except ImportError:
    pass

from .material_config import MaterialConfig
from .compiler_type import CompilerType
from .project_config import ProjectConfig

from lazurite import util
from lazurite.material import Material
from lazurite.material.shader_pass.shader_definition import ShaderPlatform
from lazurite.material.stage import ShaderStage
from lazurite.compiler.shaderc import ShadercCompiler, generate_bgfx_defines
from lazurite.compiler.dxc import DxcCompiler
from lazurite.compiler.macro_define import MacroDefine
from lazurite.material.shader_pass import Pass
from lazurite.material.shader_pass.variant import Variant
from lazurite.material.shader_pass.shader_definition import ShaderDefinition
from lazurite.tempfile import CustomTempFile


def _merge_source_by_name(
    name: str,
    platforms: list[ShaderPlatform],
    merge_source: list[str],
    cache: dict[str, tuple[str, set[ShaderPlatform]]],
):
    mat = None
    for platform in platforms:
        for path in merge_source:
            is_binary_file = path.endswith(Material.EXTENSION)
            found_platform = False
            if path in cache:
                cache_name, cache_platforms = cache[path]
                if cache_name == name and platform in cache_platforms:
                    found_platform = True
                    if is_binary_file:
                        temp_mat = Material.load_bin_file(path)
                    else:
                        temp_mat = Material.load_minimal_json(path)
                    if mat is None:
                        mat = temp_mat
                    else:
                        mat.merge_variants(temp_mat)
            else:
                if is_binary_file:
                    temp_mat = Material.load_bin_file(path)
                else:
                    temp_mat = Material.load_minimal_json(path)
                mat_platforms = temp_mat.get_platforms()
                if temp_mat.name == name and platform in mat_platforms:
                    found_platform = True
                    if mat is None:
                        mat = temp_mat
                    else:
                        mat.merge_variants(temp_mat)
                cache[path] = (temp_mat.name, mat_platforms)
            if found_platform:
                break
    return mat


def _merge_source_by_path(
    name: str,
    platforms: list[ShaderPlatform],
    merge_source: list[str],
    cache: dict[str, tuple[str, set[ShaderPlatform]]],
):
    mat = None
    for platform in platforms:
        for path in merge_source:
            if os.path.basename(path) not in (
                name + ext for ext in (Material.EXTENSION, Material.JSON_EXTENSION)
            ):
                continue
            is_binary_file = path.endswith(Material.EXTENSION)
            found_platform = False
            if path in cache:
                if platform in cache[path][1]:
                    found_platform = True

                    if is_binary_file:
                        temp_mat = Material.load_bin_file(path)
                    else:
                        temp_mat = Material.load_minimal_json(path)

                    if mat is None:
                        mat = temp_mat
                    else:
                        mat.merge_variants(temp_mat)
            else:
                if is_binary_file:
                    temp_mat = Material.load_bin_file(path)
                else:
                    temp_mat = Material.load_minimal_json(path)

                mat_platforms = temp_mat.get_platforms()
                if platform in mat_platforms:
                    found_platform = True
                    if mat is None:
                        mat = temp_mat
                    else:
                        mat.merge_variants(temp_mat)
                cache[path] = (temp_mat.name, mat_platforms)
            if found_platform:
                break
    return mat


def _merge_source_materials(
    mat_dir: os.DirEntry,
    platforms: list[ShaderPlatform],
    merge_source: list[str],
    material_cache: dict[str, tuple[str, set[ShaderPlatform]]],
):
    name = mat_dir.name
    use_name = False
    path = os.path.join(mat_dir, "material.json")
    if os.path.isfile(path):
        with open(path) as f:
            json_data = pyjson5.load(f)
        if "name" in json_data:
            name = json_data["name"]
            use_name = True

    if use_name:
        return _merge_source_by_name(name, platforms, merge_source, material_cache)
    else:
        return _merge_source_by_path(name, platforms, merge_source, material_cache)


def _generate_defines(
    config: ProjectConfig,
    material: Material,
    mat_config: MaterialConfig,
    shader_pass: Pass,
    variant: Variant,
):
    defines = config.macros[:]
    if mat_config.compiler_type is CompilerType.SHADERC:
        defines.append(MacroDefine("BGFX_CONFIG_MAX_BONES", 4))

    defines.extend(MacroDefine(f"s_{s.name}_REG", s.reg1) for s in material.buffers)

    if shader_pass.name in mat_config.macro_overwrite_pass:
        defines.extend(mat_config.macro_overwrite_pass[shader_pass.name])
    else:
        defines.append(MacroDefine(util.generate_pass_name_macro(shader_pass.name)))

    for key, value in variant.flags.items():
        if (
            key in mat_config.macro_overwrite_flags
            and value in mat_config.macro_overwrite_flags[key]
        ):
            defines.extend(mat_config.macro_overwrite_flags[key][value])
        else:
            defines.append(MacroDefine(util.generate_flag_name_macro(key, value)))

    return defines


def _compile_bgfx_shader_async(
    shaderc_compiler: ShadercCompiler,
    code_path: str,
    stage: ShaderStage,
    platform: ShaderPlatform,
    varying_path: str,
    include: list[str],
    defines: list[MacroDefine],
    options: list[str],
):
    if stage == ShaderStage.Compute:
        compiled_shader = shaderc_compiler.compile(
            code_path, platform, stage, None, include, defines, options
        )
    else:
        parser = pcpp.Preprocessor()
        parser.line_directive = None

        varying_defines = defines + generate_bgfx_defines(platform, stage)
        for macro in varying_defines:
            parser.define(macro.format_cpp())

        with open(varying_path) as f:
            parser.parse(f)

        with CustomTempFile("w+") as f:
            parser.write(f)
            f.close()
            # f.flush()

            compiled_shader = shaderc_compiler.compile(
                code_path, platform, stage, f.name, include, defines, options
            )

    return compiled_shader


def _get_material_folders(proj_config: ProjectConfig, project_path: str):
    material_folders: set[pathlib.Path] = set()
    proj_path = pathlib.Path(project_path)
    for pattern in proj_config.include_patterns:
        for path in proj_path.glob(pattern):
            if path.is_dir() and not any(
                path.match(p) for p in proj_config.exclude_patterns
            ):
                material_folders.add(path)
    return sorted(list(material_folders))


def _validate_glsl_code(
    shader: ShaderDefinition,
    opengl_context: "moderngl.Context",
    defines: list[MacroDefine],
):
    code = shader.bgfx_shader.shader_bytes.decode()

    # Hacky solution for explicitly specifying GLSL version.
    if not code.startswith("#version"):
        version_string = shader.platform.name[-3:]
        if shader.platform in (ShaderPlatform.ESSL_300, ShaderPlatform.ESSL_310):
            version_string += " es"
        code = f"#version {version_string}\n" + code

    # Try to compile GLSL shader.
    try:
        if shader.stage is ShaderStage.Compute:
            opengl_context.compute_shader(code)
        elif shader.stage is ShaderStage.Vertex:
            opengl_context.program(vertex_shader=code)
        else:
            opengl_context.program(fragment_shader=code)
    except moderngl.Error as e:
        log = list(e.args)
        log.extend(
            (
                f"Stage: {shader.stage.name}",
                f"Platform: {shader.platform.name}",
                f"Defines: {[d.format_cpp() for d in defines]}",
            )
        )

        log = "\n".join(log)
        raise Exception(log) from None


def compile(
    project_path: str,
    profiles: list[str],
    output_folder: str = "",
    material_patterns: list[str] = None,
    exclude_material_patterns: list[str] = None,
    defines: list[MacroDefine] = None,
    shaderc_path: str = None,
    dxc_path: str = None,
    shaderc_args: list[str] = None,
    dxc_args: list[str] = None,
    max_workers: int = None,
    validate: bool = True,
):
    if not os.path.isdir(project_path):
        raise Exception(f'Failed to compile project: "{project_path}" is not a folder.')

    if profiles is None:
        profiles = []
    if shaderc_args is None:
        shaderc_args = []
    if dxc_args is None:
        dxc_args = []
    if material_patterns is None:
        material_patterns = []
    if exclude_material_patterns is None:
        exclude_material_patterns = []

    proj_config = ProjectConfig()
    proj_config.read_json_file(os.path.join(project_path, "project.json"), profiles)
    platforms_set = set(proj_config.platforms)

    if material_patterns:
        proj_config.include_patterns = [
            os.path.relpath(m, project_path) for m in material_patterns
        ]
        proj_config.exclude_patterns = []
    if exclude_material_patterns:
        proj_config.exclude_patterns.extend(
            (os.path.relpath(m, project_path) for m in exclude_material_patterns)
        )

    shaderc_compiler: ShadercCompiler = None
    dxc_compiler: DxcCompiler = None
    opengl_context: "moderngl.Context" = None

    validate_glsl_code = validate and "moderngl" in sys.modules

    # {path: (name, {platforms})}
    material_cache: dict[str, tuple[str, set[ShaderPlatform]]] = {}

    for mat_dir in _get_material_folders(proj_config, project_path):
        shaders: list[ShaderDefinition] = []
        arg_defines: list[list[MacroDefine]] = []
        arg_code_path: list[str] = []
        arg_stage: list[ShaderStage] = []
        arg_platform: list[ShaderPlatform] = []
        arg_varying: list[str] = []
        arg_entry_point: list[str] = []

        print(mat_dir.name)

        mat_config = MaterialConfig()
        mat_config.read_from_json_file(os.path.join(mat_dir, "config.json"))

        # Target platforms AND platforms supported by material.
        compilable_platforms = platforms_set.intersection(
            mat_config.supported_platforms
        )

        # Load and merge vanilla target platform materials.
        material = (
            _merge_source_materials(
                mat_dir, proj_config.platforms, proj_config.merge_source, material_cache
            )
            or Material()
        )

        # If it failed to load any source materials.
        if not material.get_platforms():
            # Load and merge vanilla materials with any platforms.
            temp_mat = _merge_source_materials(
                mat_dir,
                set(ShaderPlatform),
                proj_config.merge_source,
                material_cache,
            )

            if temp_mat:
                material = temp_mat
            elif proj_config.merge_source:
                # Display a warning if no valid merge source was ever found
                # but merge_source in project config is not empty.
                print(f"Warning! Failed to find merge source for {mat_dir.name}")

            # Add necessary platforms.
            material.add_platforms(compilable_platforms)
            # Remove other unwanted platforms.
            material.remove_platforms(
                set(ShaderPlatform).difference(compilable_platforms)
            )
        else:
            material.add_platforms(compilable_platforms)

        material.load_unpacked_material(mat_dir)

        # Gather shaders for compilation.
        for shader_pass in material.passes:
            for variant in shader_pass.variants:
                for shader in variant.shaders:
                    if shader.platform not in compilable_platforms:
                        continue

                    file_overwrite = mat_config.file_overwrite_pass.get(
                        shader_pass.name, mat_config.file_overwrite_default
                    )
                    code_path = os.path.normpath(
                        os.path.join(mat_dir, file_overwrite.get_stage(shader.stage))
                    )
                    if not os.path.isfile(code_path):
                        continue

                    if mat_config.compiler_type is CompilerType.SHADERC:
                        varying_path = None
                        if shaderc_compiler is None:
                            shaderc_compiler = ShadercCompiler(shaderc_path)
                        if shader.stage is not ShaderStage.Compute:
                            varying_path = os.path.normpath(
                                os.path.join(mat_dir, file_overwrite.varying)
                            )
                            if not os.path.isfile(varying_path):
                                print(
                                    f'Varying file "{varying_path}" was not found! Skipping current shader.'
                                )
                                continue
                        arg_varying.append(varying_path)
                    else:
                        if dxc_compiler is None:
                            dxc_compiler = DxcCompiler(dxc_path)
                        arg_entry_point.append(
                            file_overwrite.entry_point or shader_pass.name
                        )

                    shaders.append(shader)
                    arg_code_path.append(code_path)
                    arg_stage.append(shader.stage)
                    arg_platform.append(shader.platform)
                    arg_defines.append(
                        _generate_defines(
                            proj_config, material, mat_config, shader_pass, variant
                        )
                        + defines
                    )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            if mat_config.compiler_type is CompilerType.SHADERC:
                results = executor.map(
                    _compile_bgfx_shader_async,
                    len(shaders) * [shaderc_compiler],
                    arg_code_path,
                    arg_stage,
                    arg_platform,
                    arg_varying,
                    len(shaders) * [proj_config.include_search_paths],
                    arg_defines,
                    len(shaders) * [mat_config.compiler_options + shaderc_args],
                )
            else:
                results = executor.map(
                    dxc_compiler.compile,
                    arg_code_path,
                    arg_platform,
                    arg_stage,
                    arg_entry_point,
                    len(shaders) * [proj_config.include_search_paths],
                    arg_defines,
                    len(shaders) * [mat_config.compiler_options + dxc_args],
                )

        for i, (shader, result) in enumerate(zip(shaders, results)):
            if mat_config.compiler_type is CompilerType.SHADERC:
                shader.bgfx_shader = result

                if validate_glsl_code and shader.platform.name.startswith(
                    ("GLSL", "ESSL")
                ):
                    if opengl_context is None:
                        opengl_context = moderngl.create_context(standalone=True)

                    _validate_glsl_code(shader, opengl_context, arg_defines[i])

            else:
                shader.bgfx_shader.shader_bytes = result

        # Filter empty shaders.
        for shader_pass in material.passes:
            for variant in shader_pass.variants:
                new_shaders = []
                for shader in variant.shaders:
                    if shader.bgfx_shader.shader_bytes:
                        new_shaders.append(shader)
                variant.shaders = new_shaders

        filepath = output_folder or os.path.dirname(project_path)
        filepath = os.path.join(filepath, mat_dir.name + Material.EXTENSION)
        with open(filepath, "wb") as f:
            material.write(f)
