from enum import Enum


class BlendMode(Enum):
    Unspecified = None
    NoneMode = 0  # None (reserved keyword)
    Replace = 1
    AlphaBlend = 2
    ColorBlendAlphaAdd = 3  # Likely deprecated.
    PreMultiplied = 4
    InvertColor = 5
    Additive = 6
    AdditiveAlpha = 7
    Multiply = 8
    MultiplyBoth = 9
    InverseSrcAlpha = 10
    SrcAlpha = 11
