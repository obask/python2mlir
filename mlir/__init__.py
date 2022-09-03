from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BasicBlock:
    items: list['Operator'] = field(default_factory=list)
    label: Optional[str] = None


@dataclass
class Region:
    blocks: list['BasicBlock'] = field(default_factory=list)

@dataclass
class ValueId:
    name: str


@dataclass
class Operator:
    name: str
    dialect: str = "py"
    return_name: ValueId = None
    operands: list[ValueId] = field(default_factory=list)
    attributes: dict[str, any] = field(default_factory=dict)
    regions: list['Region'] = field(default_factory=list)

    def region_from_operators(self, op: list['Operator']):
        self.regions.append(Region([BasicBlock(op)]))
