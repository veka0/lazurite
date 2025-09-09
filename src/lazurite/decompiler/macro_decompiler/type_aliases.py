"This file contains commonly used type aliases"

FlagName = str
FlagValue = str
ShaderFlags = dict[FlagName, FlagValue]

FlagDefinition = dict[FlagName, list[FlagValue]]
"A list of all flag values for a given flag name"


ShaderCode = str
FunctionName = str


ShaderLineIndex = int
"Unique index of a unique line of code"

ShaderLine = str
"A single line of code"
