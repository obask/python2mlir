from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


@dataclass
class ValueId:
    name: str


@dataclass
class SimpleType:
    value: str


@dataclass
class BlockLabel:
    name: str
    params: List[Tuple[ValueId, SimpleType]] = field(default_factory=list)


@dataclass
class BasicBlock:
    items: List['Operator'] = field(default_factory=list)
    label: Optional[BlockLabel] = None


@dataclass
class Region:
    blocks: List[BasicBlock] = field(default_factory=list)


@dataclass
class Operator:
    name: str
    dialect: str = "py"
    return_name: ValueId = None
    return_type: SimpleType = None
    operands: List[ValueId] = field(default_factory=list)
    operands_types: List[SimpleType] = field(default_factory=list)
    attributes: Dict[str, any] = field(default_factory=dict)
    regions: List[Region] = field(default_factory=list)

    def region_from_operators(self, op: list['Operator']):
        self.regions.append(Region([BasicBlock(op)]))


@dataclass
class FunctionTypeAttr:
    types: List[SimpleType] = field(default_factory=list)
    returns: SimpleType = None
