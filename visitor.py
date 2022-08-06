import _ast
import ast

from mlir.model import Operator, Region, BasicBlock


class PyVisitor(ast.NodeVisitor):
    some_int: int

    #     mod = Module(stmt* body, type_ignore* type_ignores)
    #         | Interactive(stmt* body)
    #         | Expression(expr body)
    #         | FunctionType(expr* argtypes, expr returns)

    @staticmethod
    def add_region(op: Operator, items: list[Operator]):
        blocks = [BasicBlock(items)]
        op.regions += Region(blocks)

    def visit_Module(self, node: ast.Module) -> Operator:
        op = Operator("py.module")
        body_ = [self.visit_stmt(stmt) for stmt in node.body]
        self.add_region(op, body_)
        return op

    def visit_stmt(self, ctx: _ast.stmt) -> Operator:
        return self.visit(ctx)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Operator:
        op = Operator("py.functionDef")
        op.attributes['args'] = str(node.args)
        op.attributes['name'] = str(node.name)
        op.attributes['returns'] = str(node.returns)
        op.attributes['type_comment'] = str(node.type_comment)
        body_ = [self.visit_stmt(stmt) for stmt in node.body]
        self.add_region(op, body_)
        return op
