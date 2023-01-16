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
class Block:
    items: List['Operator'] = field(default_factory=list)
    label: Optional[BlockLabel] = None

@dataclass
class Operator:
    name: str
    dialect: str = "py"
    return_names: List[ValueId] = field(default_factory=list)
    return_types: List[SimpleType] = field(default_factory=list)
    arguments: List[ValueId] = field(default_factory=list)
    argument_types: List[SimpleType] = field(default_factory=list)
    attributes: Dict[str, any] = field(default_factory=dict)
    blocks: List[Block] = field(default_factory=list)

    def region_from_operators(self, op: list['Operator']):
        self.blocks.append(Block(op))


@dataclass
class FunctionTypeAttr:
    types: List[SimpleType] = field(default_factory=list)
    returns: SimpleType = None
