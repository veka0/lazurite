# Projects

"Projects" in lazurite represent a group of related materials that will be compiled and packaged together. Thinking about shaders as projects rather than
individual materials allows for easier development, greater code reusability across projects and in general it just makes more sense.
Projects in lazurite are compiled using the [build](commands.md#build) command.

!!!note "Compiling shaders"

    You need a shader compiler executable in order to compile shaders from source code. See [build](commands.md#build) command for details about available compilers.

## Project file structure

Project is a folder that may contain `project.json` and unpacked materials (see [material format](material.md)). Each material can also additionally contain `config.json` and `shaders/` folder with shader source code (can be changed in `config.json`).

```
myProject/
├─ Actor/
│  ├─ ...
├─ RenderChunk/
│  ├─ ...
│  ├─ config.json
├─ project.json
```

### project.json

This file is used for configuring project-wide settings, which are represented with profiles.
Custom profiles can be activated when using a [build](commands.md#build) command, with a `--profile` argument.

```json
{
  "base_profile": {
    "macros": ["DEBUG", "FOCAL_LENGTH 12.5"],
    "platforms": ["Direct3D_SM65", "ESSL_310"],
    "merge_source": ["../../vanilla/windows/"],
    "include_patterns": "*",
    "exclude_patterns": [".*", "_*"]
  },
  "profiles": {
    "profileExample": {
      "macros": ["DEBUG", "FOCAL_LENGTH 12.5"],
      "platforms": ["Direct3D_SM65", "ESSL_310"],
      "merge_source": ["../../vanilla/windows/"],
      "include_patterns": "*",
      "exclude_patterns": [".*", "_*"]
    }
  }
}
```

| Property       | Description     |
| -------------- | --------------- |
| `base_profile` | Base profile    |
| `profiles`     | Custom profiles |

#### Profile schema

| Property           | Description                                                                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `macros`           | List of macros                                                                                                                                   |
| `platforms`        | List of [platforms](platforms.md) targetted by the project                                                                                       |
| `merge_source`     | List of individual materials or folders with materials that will be used for merging                                                             |
| `include_patterns` | Glob patterns (string or list of strings) used for searching material folders in a project, by default `["*"]`                                   |
| `exclude_patterns` | Glob patterns (string or list of strings) that exclude folders in a project from being considered as material folders, by default `[".*", "_*"]` |

!!!info "Glob patterns"

    Glob pattern support is provided by [pathlib](https://docs.python.org/3/library/pathlib.html) python library, which also adds an additional
    `**` syntax for recursive matches.

!!!tip "Default file patterns"

    With default values of `include_patterns` set to `["*"]` and `exclude_patterns` set to `[".*", "_*"]`, all folders in project root will be considered as material folders,
    unless they start with a dot `.` or an underscore `_`. Even if the folder is empty or doesn't have any meaningful data, it will still be compiled and generate
    a material in the end.

#### Profile merging rules

When building a project, multiple profiles can be specified at the same time, properties of which then will be merged together. In general, profile merging rules
can be described as follows:

1. Properties from custom profiles are added together.
2. Base profile property is only used if none of the activated custom profiles overwrite that property.

For example, if base profile specifies platforms for android and windows, and you don't activate any custom profiles, project will be compiled for both platforms.
But if you activate custom ios profile, which only has an ios platform, then project will be compiled only for ios. But if you activate both android and ios profiles, their
platforms will be added together and project will now be compiled for ios and android.

This approach allows to support numerous use cases using the same simple rules. For example, you can have profiles for individual versions (release, preview) that change `merge_source`,
profiles for specific platforms (`platforms`), features or configs (`macros`), inclusion or exclusion of specific materials (`include_patterns`, `exclude_patterns`).

### config.json

This file contains per-material compilaton settings.

```json
{
  "compiler": {
    "type": "dxc",
    "options": ["-no-warnings"]
  },
  "supported_platforms": ["Direct3D_SM65", "ESSL_310"],
  "macro_overwrite": {
    "flags": {
      "Fancy": {
        "On": "FANCY",
        "Off": []
      }
    },
    "passes": {
      "Transparent": "TRANSPARENT",
      "AlphaTest": ["ALPHA_TEST"]
    }
  },
  "file_overwrite": {
    "default": {
      "entry_point": "main",
      "fragment": "shaders/fragment.sc",
      "vertex": "shaders/vertex.sc",
      "compute": "shaders/compute.sc",
      "unknown": "shaders/unknown.sc",
      "varying": "shaders/varying.def.sc"
    },
    "passes": {
      "Transparent": {
        "entry_point": "main",
        "fragment": "shaders/fragment.sc",
        "vertex": "shaders/vertex.sc",
        "compute": "shaders/compute.sc",
        "unknown": "shaders/unknown.sc",
        "varying": "shaders/varying.def.sc"
      }
    }
  }
}
```

| Property              | Description                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `compiler`            | Compiler settings. `type` can be `dxc` (for RTX shaders) or `shaderc` (for BGFX shaders). `shaderc` is the default compiler. `options` is a list of additional aguments that will be passed to the compiler |
| `supported_platforms` | List of [platforms](platforms.md) supported by material. By default, all platforms are supported                                                                                                            |
| `macro_overwrite`     | Allows to overwrite autogenerated flag or pass macros                                                                                                                                                       |
| `file_overwrite`      | Allows to overwrite shader file paths and compute entry point per pass or globally. Note that entry point overwrite is only supported for DXC compiler                                                      |

???note "Macro generation rules"

    Both passes and flags are formatted from camel case to snake case, according to the following rules:

    1. aA -> a_A (insert underscore before a new word begins)
    2. AAa -> A_Aa (insert underscore before a new word begins, if previous ended in capital letter)
    3. 00X -> 00_X (insert underscore after a number)

    After formatting, pass names are appended with `_PASS` (unless they already end with it), while flag names and keys are joined with a double underscore `__`.

    For example, `AlphaTest` pass will generate as `ALPHA_TEST_PASS` while `Emissive` flag with a value of `EmissiveOnly` with generate as `EMISSIVE__EMISSIVE_ONLY`

???note "Default file overwrites"

    If not specified, the following file paths are used by default: `shaders/fragment.sc`, `shaders/vertex.sc`, `shaders/compute.sc`, `shaders/unknown.sc`, `shaders/varying.def.sc`.

    Default entry point value is empty string, which means that entry point name will be equal to shader pass name.

## Compilation pipeline

Platforms specified in project and material configs are very important during compilation. Think of project platforms as platforms that you wish to target with your project,
while material platforms are platforms that a specific material can be compiled for. Project is compiled one material at a time.

At first, lazurite loads and merges together materials from merge paths which have at least one platform from a list of `platforms` in project config. Materials are chosen for merging if they have the same material name,
if it's specified in material.json, otherwise they are merged if they have a base file name that matches folder name of the material in a project. Output material will always have the same file name as material folder in the project.

If no materials with matching platforms can be found, it will instead merge materials with any platforms, add compilable platforms (platforms that are both in project and material configs) and remove any other platforms.

If the final merged material doesn't have all compileable platforms, remaining platforms will be added to it automatically. So having vanilla materials for every platform is not necessary.

Then the resulting material gets additionally merged with any material data in the project material folder. This allows you to make any targetted changes that will overwrite properties of the final material.

Shaders will be compiled for platforms that are both in project and material config.

???tip "Automatic register binding"

    Did you know? Lazurite passes buffer registers as macros to both SHADERC and DXC compilers. The format is `s_<BufferName>_REG`, for example `s_MatTexture_REG`. If you are using
    the following [bgfx_shader.sh](https://github.com/SurvivalApparatusCommunication/RenderDragonSourceCodeInv/blob/1.20.60/include/bgfx_shader.sh) or
    [bgfx_compute.sh](https://github.com/SurvivalApparatusCommunication/RenderDragonSourceCodeInv/blob/1.20.60/include/bgfx_compute.sh), you can even use AUTOREG macros that automatically
    set registers and bindings to that macro, based only on buffer name.

## Material changes merging rules

As mentioned previously, you can specify individual changes instead of the whole material in a project material folder, and those changes will be applied to the final material after merging, but before compiling shaders.

In general, any fields that you specify will overwrite fields of the source material. For example, if you have just a material.json with only a `parent` property inside, it will only change the name of the material parent and nothing else.
Overwriting properties of uniforms, buffers or passes can be done in the same way, except if the `name` in a uniform, buffer or pass json file is provided, it will modify an object with the same name. But if the name is not provided,
it will instead treat filename as a name of object to be modified. If the object cannot be found by name, it will instead be appended to the material, which allows to easily add new buffers, passes or uniforms, by adding
new json files, no material.json editing is required (so no need to specify `uniforms`, `buffers` or `passes`). Although deleting any objects can only be done by specifying a list of names
in material.json with unwanted entries removed. A manual overwrite of material.json takes priority over additional objects that are added into their respective folders.

!!!warning

    Changing properties of individual variants, including replacing compiled shaders is currently unsupported. You have to provide full data from `variants` object in a shader pass json file, as well as all files with compiled shaders
    from that shader pass.

!!!warning "Encryption"

    If any of the merge sources for a specific material are encrypted, compiled material will also be encrypted. This is necessary to protect 3rd party IP, which in turn protects this project from potential legal action.
