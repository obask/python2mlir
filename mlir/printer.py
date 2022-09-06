import dataclasses
from dataclasses import dataclass
from typing import Dict, List

from mlir import Operator, Region, BasicBlock, FunctionTypeAttr


@dataclass
class DefaultPrinter:
    sb: list[str] = dataclasses.field(default_factory=list)

    def render_block(self, block: BasicBlock, indent: str) -> list[str]:
        new_indent = f"{indent}    "
        if block.label:
            args_string = ", ".join(f"{n.name}: {t.value}" for n, t in block.label.params)
            self.sb.append(f"{indent}{block.label.name}({args_string}):\n")
        for op in block.items:
            self.render_operator(op, new_indent)
            self.sb.append("\n")
        return self.sb

    def render_region(self, region: Region, indent: str) -> list[str]:
        self.sb.append("{\n")
        for block in region.blocks:
            self.render_block(block, indent)
            # self.sb.append("\n")
        self.sb.append(indent + "}")
        return self.sb

    def render_regions(self, regions: list[Region], indent: str):
        if not regions:
            return
        self.sb.append("(")
        if regions:
            self.render_region(regions[0], indent)
        for region in regions[1:]:
            self.sb.append(", ")
            self.render_region(region, indent)
        self.sb.append(")")

    def render_attributes(self, attributes: Dict, indent: str = "") -> List[str]:
        items = []
        for k, attr in sorted(attributes.items()):
            if isinstance(attr, FunctionTypeAttr):
                arg_types = ", ".join(t.value for t in attr.types)
                items.append(f"{k}=({arg_types}) -> {attr.returns.value}")
            elif isinstance(attr, str):
                items.append(f'{k}="{attr}"')
            else:
                items.append(f"{k}={attr}")
        self.sb.append(" {")
        self.sb.append(", ".join(items))
        self.sb.append("}")
        return self.sb

    def render_operator(self, op: Operator, indent: str = "") -> list[str]:
        lhs = f"{op.return_name.name} = " if op.return_name else ""
        operands1 = ", ".join([it.name for it in op.operands])
        self.sb.append(f"{indent}{lhs}\"{op.dialect}.{op.name}\"({operands1}) ")
        self.render_regions(op.regions, indent)
        if op.attributes:
            self.render_attributes(op.attributes)
        operand_types = ", ".join(t.value for t in op.operands_types)
        if op.return_name:
            return_type = op.return_type.value if op.return_type else "!_.Any"
            self.sb.append(f" : ({operand_types}) -> {return_type}")
        else:
            self.sb.append(f" : ({operand_types}) -> ()")
        return self.sb
