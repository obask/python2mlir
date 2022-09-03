import dataclasses
from dataclasses import dataclass

from mlir import Operator, Region, BasicBlock


@dataclass
class DefaultPrinter:
    sb: list[str] = dataclasses.field(default_factory=list)

    def render_block(self, block: BasicBlock, indent: str) -> list[str]:
        new_indent = f"{indent}    "
        if block.label:
            self.sb.append(new_indent + str(block.label) + "\n")
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

    def render_operator(self, op: Operator, indent: str = "") -> list[str]:
        lhs = f"{op.return_name.name} = " if op.return_name else ""
        operands1 = ", ".join([it.name for it in op.operands])
        self.sb.append(f"{indent}{lhs}\"{op.dialect}.{op.name}\"({operands1}) ")
        self.render_regions(op.regions, indent)
        if op.attributes:
            self.sb.append(str(op.attributes))
        operand_types = ", ".join("!_.Any" for _ in op.operands)
        if op.return_name:
            self.sb.append(f" : ({operand_types}) -> !_.Any")
        else:
            self.sb.append(f" : ({operand_types}) -> ()")
        return self.sb
