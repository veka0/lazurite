from enum import Enum


class ShaderStage(Enum):
    Vertex = 0
    Fragment = 1
    Compute = 2
    Unknown = 3
