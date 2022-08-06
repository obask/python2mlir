from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BasicBlock:
    regions: list['Operator'] = field(default_factory=list)
    name: Optional[str] = None


@dataclass
class Region:
    regions: list['BasicBlock'] = field(default_factory=list)


@dataclass
class Operator:
    name: str
    attributes: dict[str, any] = field(default_factory=dict)
    regions: list['Region'] = field(default_factory=list)
