# Commands

Main way of interacting with lazurite is with a command line interface, which can have different syntax, depending on the installation method

```sh
lazurite COMMAND [INPUTS ...] [ARGUMENTS ...]
```

```sh
lazurite.exe COMMAND [INPUTS ...] [ARGUMENTS ...]
```

```sh
python -m lazurite COMMAND [INPUTS ...] [ARGUMENTS ...]
```

Here is a cheatsheet of what each command does

| Command                                | Description                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| [**unpack**](commands.md#unpack)       | Unpacks input materials                                                                                      |
| [**pack**](commands.md#pack)           | Packs materials back into `material.bin` files                                                               |
| [**label**](commands.md#label)         | Adds a comment with debug information to plain text shaders (GLSL, ESSL, Metal)                              |
| [**clear**](commands.md#clear)         | Clears compiled shaders in materials, while removing encryption                                              |
| [**restore**](commands.md#restore)     | Restores GLSL or SC source code from Android materials and varying.def.sc from any materials                 |
| [**build**](commands.md#build)         | Compiles all materials and shaders in a project                                                              |
| [**info**](commands.md#info)           | Displays useful information about input material                                                             |
| [**serialize**](commands.md#serialize) | Generates minimal json from material bin files that can be used as [merge source](project.md#profile-schema) |

## unpack

```sh
lazurite unpack [MATERIALS ...] [--sort-flags] [--skip-shaders] [-o OUTPUT]
```

| Argument         | Description                                     | Default           |
| ---------------- | ----------------------------------------------- | ----------------- |
| `--sort-flags`   | Sorts variants and flags alphabeticaly          |                   |
| `--skip-shaders` | Don't unpack compiled shaders                   |                   |
| `-o` `--output`  | Output folder, where materials will be unpacked | current directory |

!!!warning

    This command won't unpack compiled shaders from encrypted materials (RTXStub)

This command unpacks input materials (`material.bin` files). You can specify multiple materials or folders with material files.
By default, it will unpack into current working directory, but optional `--output`
argument can be used to specify output directory instead. `--sort-flags` can be used to sort flags within variants and variants
by flags, which might be useful when diffing unpacked materials. See [material format](material.md) for details on the unpacked
material format.

Example usage

```sh
lazurite unpack Actor.bin folderWithMaterials/ RenderChunk.bin --sort-flags -o outputFolder/
```

This command will unpack `Actor.bin`, `RenderChunk.bin` and all materials in `folderWithMaterials/` into the `outputFolder/` while sorting their variants and flags.

## pack

```sh
lazurite pack [MATERIALS ...] [-o OUTPUT]
```

| Argument        | Description                                          | Default           |
| --------------- | ---------------------------------------------------- | ----------------- |
| `-o` `--output` | Output folder, where packed materials will be stored | current directory |

This command packs unpacked input materials back into `material.bin` files. You can specify as an input:

1. Path to `material.json` file inside of unpacked material folder
2. Path to unpacked material folder (if it has `material.json` inside)
3. Path to a folder with unpacked materials (if it doesn't have `material.json` but each material inside of it does)

Multiple inputs can be specified at the same time. By default, materials will be packed into current working directory, but `--output` can be used
to specify a different output directory.

Example usage

```sh
lazurite pack Actor/ folderWithMaterials/ RenderChunk/material.json -o outputFolder/
```

This command will pack `Actor` and `RenderChunk` materials as well as all materials from `folderWithMaterials/` into the `outputFolder/`.

## label

```sh
lazurite label [MATERIALS ...] [-o OUTPUT]
```

| Argument        | Description                                                    | Default           |
| --------------- | -------------------------------------------------------------- | ----------------- |
| `-o` `--output` | Output folder, where labeled material bin files will be stored | current directory |

Adds a comment with debug information at the top of shader programs. It's added to
every plain text shader (ESSL, GLSL, Metal) inside of `material.bin` file. Here is an example of what it looks like:

```c
// Shader Information:
// - Name: RenderChunk
// - Pass: Transparent
// - Platform: ESSL_310
// - Stage: Fragment
// - Variant: 0
// - Variant Supported: True
// - Variant Flags:
//    - Instancing: On
//    - RenderAsBillboards: On
//    - Seasons: Off
```

This information can be useful when using graphics debugger such as RenderDoc.
As an input, you can specify multiple `material.bin` files or folders with them.
`--output` can be used to specify output folder where labeled `material.bin` files will be stored
(by default, it's the current working directory).

Example usage

```sh
lazurite label RenderChunk.material.bin folderWithMaterials/ -o outputFolder/
```

This command will label `RenderChunk.material.bin` and all materials from `folderWithMaterials/` and save them
as `material.bin` files in the `outputFolder/`.

## clear

```sh
lazurite clear [MATERIALS ...] [-o OUTPUT]
```

| Argument        | Description                                                    | Default           |
| --------------- | -------------------------------------------------------------- | ----------------- |
| `-o` `--output` | Output folder, where cleared material bin files will be stored | current directory |

Wipes all compiled shaders, while removing encryption. This command can be useful when you need a light-weight
merge source or when you want to compile RTX shader that shouldn't be encrypted.
Note that if you unpack resulting material, its compiled shader files will be empty.

Example usage

```sh
lazurite clear RTXStub.material.bin -o outputFolder/
```

## restore

```sh
lazurite restore [MATERIALS ...] [--timeout SECONDS] [--max-workers WORKERS] [--no-processing] [--merge-stages] [--split-passes] [-o OUTPUT]
```

| Argument          | Description                                                            | Default           |
| ----------------- | ---------------------------------------------------------------------- | ----------------- |
| `-o` `--output`   | Output folder, where restored shaders will be stored                   | current directory |
| `--max-workers`   | Maximum number of processes to use                                     | CPU cores         |
| `--timeout`       | Maximum time allowed for slow search algorithm, in seconds             | 10                |
| `--merge-stages`  | Generates shader stages in a single file                               |                   |
| `--split-passes`  | Generates separate files for individual passes                         |                   |
| `--no-processing` | Disable additional processing used for converting from GLSL to BGFX SC |                   |

!!!warning

    This command won't restore shaders from encrypted materials (RTXStub)

Attempts to restore GLSL or BGFX SC source code from ESSL_300 or ESSL_310 materials (mainly used in Android) and varying.def.sc from any materials.
It works by identifying the differences between individual shader variants and trying to find matching macro conditionals.

This command supports multiprocessing (utilizes multiple CPU cores) for faster restoring times and `--max-workers` argument can be used to specify
max number of processes that will be created. Each process restores its own material.

When restoring macro conditionals, lazurite will first try to utilize fast algorithm, and if that fails, it will display `slow search` message
in the console and try the slow search algorithm (brute-force), which has a time limit that can be set with `--timeout`. If slow search fails
to find the conditional in provided time, it will display a `not found` message in the console and instead will use the best approximate solution
it could find, which looks like this in code:

```c
// Approximation, matches 256 cases out of 320
#if defined(ALPHA_TEST_PASS) || (defined(OPAQUE_PASS) && defined(UI_ENTITY__DISABLED))
```

When restoring BGFX SC source code, lazurite will also add `// Attention!` comment next to code that needs special attention, as it can't be edited automatically.
It hints at a potential matrix multiplication or matrix element access.

For example:

```glsl
vec4 jitterVertexPosition(vec3 worldPosition) {
    mat4 offsetProj = Proj;
    offsetProj[2][0] += SubPixelOffset.x; // Attention!
    offsetProj[2][1] -= SubPixelOffset.y; // Attention!
    return ((offsetProj) * (((View) * (vec4(worldPosition, 1.0f))))); // Attention!
}
```

Above code would have to be edited manually to look like this:

```glsl
vec4 jitterVertexPosition(vec3 worldPosition) {
    mat4 offsetProj = Proj;
    #if BGFX_SHADER_LANGUAGE_GLSL
    offsetProj[2][0] += SubPixelOffset.x;
    offsetProj[2][1] -= SubPixelOffset.y;
    #else
    offsetProj[0][2] += SubPixelOffset.x;
    offsetProj[1][2] -= SubPixelOffset.y;
    #endif
    return mul(offsetProj, mul(View, vec4(worldPosition, 1.0f)));
}
```

However keep in mind that `mul()` can't be used for vector component-wise multiplication, and `[x][y]` syntax might also refer to accessing vector component of an array element
instead of matrix element, in which case there is no need to change the index order.

Example usage

```sh
lazurite restore RenderChunk.material.bin folderWithMaterials/
```

This command will restore BGFX SC for `RenderChunk.material.bin` and for all materials from `folderWithMaterials/` and save them in the current working directory.

## build

```sh
lazurite build [PROJECTS ...] [--max-workers WORKERS] [--dxc DXC] [--shaderc SHADERC] [--dxc-args [ARGS ...]] [--shaderc-args [ARGS ...]] [-p [PROFILES ...]] [-d [DEFINES ...]] [-m [MATERIALS ...]] [-e [EXCLUDE ...]] [-o OUTPUT]
```

| Argument            | Description                                                                                                                                       | Default                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `-o` `--output`     | Output folder, where compiled materials will be stored                                                                                            | project directory                                  |
| `--max-workers`     | Maximum number of threads (compiler instances) to use                                                                                             | CPU cores times 5                                  |
| `--dxc`             | DXC compiler command                                                                                                                              | Tries to execute `dxc` first, then `./dxc`         |
| `--dxc-args`        | DXC arguments                                                                                                                                     |                                                    |
| `--shaderc`         | SHADERC compiler command                                                                                                                          | Tries to execute `shaderc` first, then `./shaderc` |
| `--shaderc-args`    | SHADERC arguments                                                                                                                                 |                                                    |
| `-p` `--profile`    | List of profiles (e.g. `-p debug, windows, preview`)                                                                                              |                                                    |
| `-d` `--defines`    | List of defines (e.g. `-d DEBUG, "SAMPLES 10"`)                                                                                                   |                                                    |
| `-m` `--materials`  | List of glob file path patterns that will be compiled as materials when building a project (overwrites `include_patterns` and `exclude_patterns`) |                                                    |
| `-e` `--exclude`    | List of glob file path patterns that will be excluded during project compilation (works with `--materials`, addtive with `exclude_patterns`)      |                                                    |
| `--skip-validation` | Do not attempt to validate GLSL or ESSL shaders                                                                                                   |                                                    |
| `--glslang`         | Glslang validator path                                                                                                                            | Tries to execute `glslang` first, then `./glslang` |

Compiles all materials from input project paths into output directory (or into project folders, if `--output` is not specified).
See [projects documentation](project.md) for more details.

Example usage

```sh
lazurite build projects/pathTracer/ -p windows, android, preview -o output/
```

This command will compile project in `projects/pathTracer/` folder, with `windows`, `android` and `preview` active profiles and
save the compiled materials in the `output/` folder

!!!info "Download DXC and SHADERC compilers"

    Shaderc is a cross platform compiler commonly used for compiling regular, non-rtx shaders.

    Download: <https://github.com/ddf8196/bgfx-mcbe/actions>

    Alternative download:
    <https://github.com/veka0/bgfx-mcbe/releases/tag/binaries>

    DXC compiler is mainly used for compiling RTX shaders, as it only supports Direct3D.

    Download: <https://github.com/microsoft/DirectXShaderCompiler/releases>

???warning "Running DXC on Linux"

    When trying to compile materials with DXC compiler on Linux you might encounter the following error:

    ```
    ./dxc error while loading shared libraries: libdxcompiler.so: cannot open shared object file: No such file or directory
    ```

    It can be solved by prefixing lazurite command with `LD_LIBRARY_PATH=<path to folder with libdxcompiler.so>`

    For example:

    ```sh
    LD_LIBRARY_PATH=libs lazurite build myAwesomeShader/
    ```

???warning "Running SHADERC on Android (Termux)"

    If you wish to compile on Android, you have to copy shaderc into your termux home directory

    ```sh
    cp path/to/shaderc ~/new/path/to/shaderc
    ```

    Make it executable

    ```sh
    chmod +x ~/new/path/to/shaderc
    ```

    And reference it in future lazurite build commands

    ```sh
    lazurite build --shaderc ~/new/path/to/shaderc myAwesomeShader/
    ```

    ---

    You might also encounter the following error:

    ```
    CANNOT LINK EXECUTABLE "/data/data/com.termux/files/home/shaderc": library "libc++_shared.so" not found: needed by main executable
    ```

    Which can be solved by copying required file into your home directory

    ```sh
    cp $PREFIX/lib/libc++_shared.so ~/
    ```

    And referencing directory with your lib file in the lazurite command, by prefixing it with `LD_LIBRARY_PATH=<path to folder with libc++_shared.so>`

    For example:

    ```sh
    LD_LIBRARY_PATH=~/ lazurite build --shaderc ~/new/path/to/shaderc myAwesomeShader/
    ```

## info

```sh
lazurite info [MATERIALS ...]
```

Shows useful information about input material(s).

Example output:

```
#### ActorBannerForwardPBR.material.bin ####
Name: ActorBannerForwardPBR
Encryption: NONE
Parent: ActorForwardPBR
Total Shaders: 544
Platforms (4):
  - Direct3D_SM40
  - Direct3D_SM50
  - Direct3D_SM60
  - Direct3D_SM65
Stages (2):
  - Fragment
  - Vertex
Passes:
  - DepthOnly: DEPTH_ONLY_PASS
  - DepthOnlyOpaque: DEPTH_ONLY_OPAQUE_PASS
  - ForwardPBRAlphaTest: FORWARD_PBR_ALPHA_TEST_PASS
  - ForwardPBROpaque: FORWARD_PBR_OPAQUE_PASS
  - ForwardPBRTransparent: FORWARD_PBR_TRANSPARENT_PASS
Flags:
  - Change_Color:
    - Multi: CHANGE_COLOR__MULTI
    - Off: CHANGE_COLOR__OFF
  - Emissive:
    - Off: EMISSIVE__OFF
  - Fancy:
    - On: FANCY__ON
  - Instancing:
    - Off: INSTANCING__OFF
    - On: INSTANCING__ON
  - MaskedMultitexture:
    - Off: MASKED_MULTITEXTURE__OFF
    - On: MASKED_MULTITEXTURE__ON
  - Tinting:
    - Disabled: TINTING__DISABLED
    - Enabled: TINTING__ENABLED
Buffers:
  - lowp texture2D BrdfLUT:
    - Reg1: 0
    - Reg2: 0
    - Unordered Access: False
    - Sampler State:
      - Texture Filter: Bilinear
      - Texture Wrap: Clamp
    - Custom Type Info:
  - lowp structBuffer DirectionalLightSources:
    - Reg1: 1
    - Reg2: 1
    - Unordered Access: True
    - Sampler State:
    - Custom Type Info:
      - Struct: LightSourceWorldInfo
      - Size: 448
  - lowp texture2D MaxFrameLuminance r32f:
    - Reg1: 3
    - Reg2: 3
    - Unordered Access: True
    - Sampler State:
    - Custom Type Info:
Uniforms (6):
  - vec4 AtmosphericScattering = [0.0, 0.0, 0.0, 0.0]
  - vec4 AtmosphericScatteringToggles = [0.0, 0.0, 0.0, 0.0]
  - vec4 BannerColors[7]
  - vec4 BannerUVOffsetsAndScales[7]
  - vec4 BlockBaseAmbientLightColorIntensity
  - mat4 Bones[8]
```

## serialize

```sh
lazurite serialize [MATERIALS ...] [-o OUTPUT]
```

| Argument        | Description                                                          | Default           |
| --------------- | -------------------------------------------------------------------- | ----------------- |
| `-o` `--output` | Output folder, where generated `.material.json` files will be stored | current directory |

Converts input material bin files into minimal json files, one file per material. Those files
can be used as a merge source for [build](commands.md#build) command, when compiling a project.

Generated json files only contain information that is necessary for compilation and nothing else, so
they are quite lightweight. All material properties are sorted alphabetically which makes generated files
invariant to changes in property sorting that occasionally occur with game updates. Sorting and small size
makes this file format perfect for storing material merge source in version control systems such as GitHub.

Example usage

```sh
lazurite serialize RenderChunk.material.bin folderWithMaterials/ -o outputFolder/
```

This command will generate json files for `RenderChunk.material.bin` and all materials from `folderWithMaterials/`
and save them in the `outputFolder/`.
