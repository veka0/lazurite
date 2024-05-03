from lazurite.material.stage import ShaderStage


class ShaderFileOverwrite:
    entry_point: str
    fragment: str
    vertex: str
    compute: str
    unknown: str
    varying: str

    def __init__(self) -> None:
        self.entry_point = ""
        self.fragment = "shaders/fragment.sc"
        self.vertex = "shaders/vertex.sc"
        self.compute = "shaders/compute.sc"
        self.unknown = "shaders/unknown.sc"
        self.varying = "shaders/varying.def.sc"

    def read_json(self, json_data: dict):
        self.entry_point = json_data.get("entry_point", self.entry_point)
        self.fragment = json_data.get("fragment", self.fragment)
        self.vertex = json_data.get("vertex", self.vertex)
        self.compute = json_data.get("compute", self.compute)
        self.unknown = json_data.get("unknown", self.unknown)
        self.varying = json_data.get("varying", self.varying)

    def get_stage(self, stage: ShaderStage):
        if stage == ShaderStage.Fragment:
            return self.fragment
        if stage == ShaderStage.Vertex:
            return self.vertex
        if stage == ShaderStage.Compute:
            return self.compute
        if stage == ShaderStage.Unknown:
            return self.unknown
