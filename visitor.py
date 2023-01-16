import _ast
import ast
from dataclasses import dataclass, field
from typing import Tuple, List, Dict

from hlir import Operator, Block, ValueId, BlockLabel, SimpleType, FunctionTypeAttr

RETURN_TYPE_KEY = "RETURN"


def op2return_name(op: Operator) -> ValueId:
    return ValueId("%" + str(id(op))[-3:])


def parse_type(t) -> SimpleType:
    if t is None:
        return SimpleType(f"()")
    elif isinstance(t, ast.Subscript):
        return SimpleType(f"!_.{ast.unparse(t)}".replace("[", "<").replace("]", ">"))
    elif isinstance(t, ast.Name):
        return SimpleType(f"!_.{t.id}")
    else:
        raise NotImplementedError(ast.unparse(t))


@dataclass
class PyVisitor(ast.NodeVisitor):
    parent_blocks: list[list[Operator]] = field(default_factory=list)
    ssa_scopes: list[dict[str, list[Operator]]] = field(default_factory=list)
    var_scopes: list[set[str]] = field(default_factory=list)
    value_types: Dict[str, SimpleType] = field(default_factory=dict)
    is_function_context: bool = False

    #     mod = Module(stmt* body, type_ignore* type_ignores)
    #         | Interactive(stmt* body)
    #         | Expression(expr body)
    #         | FunctionType(expr* argtypes, expr returns)

    def process_region(self, op: Operator, statements: list[_ast.stmt | _ast.expr], _label: str):
        current = []
        self.parent_blocks.append(current)
        for stmt in statements:
            if isinstance(stmt, _ast.expr):
                current.append(self.visit_expr(stmt))
            else:
                current.append(self.visit_stmt(stmt))
        op.region_from_operators(self.parent_blocks.pop())

    def process_operand(self, op: Operator, expr: _ast.expr, _label: str):
        if not expr:
            return
        if isinstance(expr, ast.Name):
            value_id = self.visit_Name(expr)
            op.arguments.append(value_id)
            op.argument_types.append(self.value_types.get(value_id.name, SimpleType("!_.Any")))
        else:
            new_operand = self.visit_expr(expr)
            new_operand.return_names.append(op2return_name(new_operand))
            self.parent_blocks[-1].append(new_operand)
            op.arguments += new_operand.return_names
            op.argument_types.append(SimpleType("!_.Any"))

    @staticmethod
    def add_region(op: Operator, items: list[Operator]):
        blocks = [Block(items)]
        op.blocks.append(Block(blocks))

    def visit_Module(self, node: ast.Module) -> Operator:
        """ Module(stmt* body, type_ignore* type_ignores) """
        op = Operator("module", dialect="builtin")
        # body_ = [self.visit_stmt(stmt) for stmt in node.body]
        # self.add_region(op, body_)
        self.process_region(op, node.body, "body")
        return op

    def visit_expr(self, ctx: _ast.expr) -> Operator:
        op = self.visit(ctx)
        if not op.return_names:
            op.return_names.append(op2return_name(op))
        return op

    def visit_stmt(self, ctx: _ast.stmt) -> Operator:
        return self.visit(ctx)

    def visit_Interactive(self, node: ast.Interactive) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Expression(self, node: ast.Expression) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Operator:
        """ FunctionDef(identifier name, arguments args, stmt* body,
            expr* decorator_list, expr? returns, string? type_comment)
        """
        self.ssa_scopes.append(dict())
        self.var_scopes.append(set())
        self.is_function_context = True
        op = Operator("func", dialect="func")
        # op.attributes['args'] = str(node.args)
        op.attributes['sym_name'] = str(node.name)
        # op.attributes['returns'] = str(node.returns)
        if node.type_comment:
            op.attributes['type_comment'] = str(node.type_comment)
        arguments = self.visit_arguments(node.args)
        function_type = FunctionTypeAttr()
        for n, t in arguments:
            self.value_types[n.name] = t
            function_type.types.append(t)
        return_type = parse_type(node.returns)
        function_type.returns = return_type
        self.value_types[RETURN_TYPE_KEY] = return_type
        self.process_region(op, node.body, "body")
        bb0 = op.blocks[0]
        bb0.label = BlockLabel("^bb0")
        bb0.label.params = arguments
        op.attributes['function_type'] = function_type
        # body_ = [self.visit_stmt(stmt) for stmt in node.body]
        # self.add_region(op, body_)
        self.ssa_scopes.pop()
        self.var_scopes.pop()
        self.is_function_context = False
        return op

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_ClassDef(self, node: ast.ClassDef) -> Operator:
        """ ClassDef(identifier name, expr* bases, keyword* keywords, stmt* body, expr* decorator_list) """
        op = Operator("class")
        op.attributes['name'] = str(node.name)
        op.attributes['bases'] = [ast.unparse(b) for b in node.bases]
        op.attributes['keywords'] = [ast.unparse(k) for k in node.keywords]
        self.process_region(op, node.body, "body")
        op.attributes['decorator_list'] = [ast.unparse(d) for d in node.decorator_list]
        return op

    def visit_Return(self, node: ast.Return) -> Operator:
        """ Return(expr? value) """
        op = Operator("return", dialect="func")
        self.process_operand(op, node.value, "value")
        # op.operands_types[0] = self.value_types[RETURN_TYPE_KEY]
        return op

    def visit_Delete(self, node: ast.Delete) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Assign(self, node: ast.Assign) -> Operator:
        """ Assign(expr* targets, expr value, string? type_comment) """
        if len(node.targets) != 1:
            raise NotImplementedError(";".join(ast.unparse(t) for t in node.targets))
        lhs = node.targets[0]
        if not isinstance(lhs, ast.Name):
            raise NotImplementedError(ast.unparse(lhs))
        if lhs.id in self.var_scopes[-1]:
            op = Operator("store")
            op.attributes['name'] = lhs.id
        elif lhs.id in self.ssa_scopes[-1]:
            store = Operator("store")
            store.attributes['name'] = lhs.id
            store.arguments.append(ValueId(f"%{lhs.id}"))
            self.ssa_scopes[-1][lhs.id].append(store)
            del self.ssa_scopes[-1][lhs.id]
            self.var_scopes[-1].add(lhs.id)
            op = Operator("store")
            op.attributes['name'] = lhs.id
        else:
            self.ssa_scopes[-1][lhs.id] = self.parent_blocks[-1]
            op = Operator("assign")
            op.return_names = [ValueId(f"%{lhs.id}")]
        # op.attributes['targets'] = str(node.targets)
        self.process_operand(op, node.value, "value")
        if node.type_comment:
            op.attributes['type_comment'] = str(node.type_comment)
        return op

    def visit_AugAssign(self, node: ast.AugAssign) -> Operator:
        """ AugAssign(expr target, operator op, expr value) """
        op = Operator("augAssign")
        if not isinstance(node.target, ast.Name):
            raise NotImplementedError(ast.unparse(node))
        op.attributes['target'] = node.target.id
        op.attributes['op'] = node.op.__class__.__dict__["__doc__"].lower()
        self.process_operand(op, node.value, "value")
        return op

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Operator:
        """ AnnAssign(expr target, expr annotation, expr? value, int simple) """
        if not isinstance(node.target, ast.Name):
            raise NotImplementedError(ast.unparse(node.target))
        if self.is_function_context:
            self.ssa_scopes[-1][node.target.id] = self.parent_blocks[-1]
            op = Operator("unrealized_conversion_cast", dialect="builtin")
            op.return_names = [ValueId(f"%{node.target.id}")]
            self.process_operand(op, node.value, "value")
            op.return_types.append(parse_type(node.annotation))
            for n, t in zip(op.return_names, op.return_types):
                self.value_types[n.name] = t

        else:
            op = Operator("annField")
            op.attributes['target'] = node.target.id
            op.attributes['annotation'] = ast.unparse(node.annotation)
            op.attributes['simple'] = node.simple
        return op

    def visit_For(self, node: ast.For) -> Operator:
        """ For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment) """
        op = Operator("for")
        self.process_region(op, [node.iter], "iter")
        self.process_region(op, node.body, "body")
        if isinstance(node.target, ast.Name):
            op.attributes['target'] = node.target.id
        else:
            raise NotImplementedError(ast.unparse(node))
        self.process_region(op, node.body, "body")
        if node.orelse:
            raise NotImplementedError(ast.unparse(node))
        op.attributes['type_comment'] = node.type_comment
        return op

    def visit_AsyncFor(self, node: ast.AsyncFor) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_While(self, node: ast.While) -> Operator:
        """ While(expr test, stmt* body, stmt* orelse) """
        op = Operator("while")
        self.process_region(op, [node.test], "test")
        self.process_region(op, node.body, "body")
        if node.orelse:
            raise ValueError(";".join(ast.unparse(x) for x in node.orelse))
        return op

    def visit_If(self, node: ast.If) -> Operator:
        """ If(expr test, stmt* body, stmt* orelse) """
        op = Operator("if")
        self.process_operand(op, node.test, "test")
        self.process_region(op, node.body, "body")
        if node.orelse:
            self.process_region(op, node.orelse, "orelse")
        return op

    def visit_With(self, node: ast.With) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_AsyncWith(self, node: ast.AsyncWith) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Raise(self, node: ast.Raise) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Try(self, node: ast.Try) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Assert(self, node: ast.Assert) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Import(self, node: ast.Import) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Global(self, node: ast.Global) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Nonlocal(self, node: ast.Nonlocal) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Expr(self, node: ast.Expr) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Pass(self, node: ast.Pass) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Break(self, node: ast.Break) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Continue(self, node: ast.Continue) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Slice(self, node: ast.Slice) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_BoolOp(self, node: ast.BoolOp) -> Operator:
        """ BoolOp(boolop op, expr* values) """
        op = Operator("boolOp")
        assert len(node.values) == 2
        op.attributes['op'] = node.op.__class__.__dict__["__doc__"].lower()
        for i, value in enumerate(node.values):
            self.process_operand(op, value, f"op{i}")
        return op

    def visit_BinOp(self, node: ast.BinOp) -> Operator:
        """ BinOp(expr left, operator op, expr right) """
        op = Operator("binOp")
        op.attributes['op'] = node.op.__class__.__dict__["__doc__"].lower()
        self.process_operand(op, node.left, "left")
        self.process_operand(op, node.right, "right")
        return op

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Lambda(self, node: ast.Lambda) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_IfExp(self, node: ast.IfExp) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Dict(self, node: ast.Dict) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Set(self, node: ast.Set) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_ListComp(self, node: ast.ListComp) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_SetComp(self, node: ast.SetComp) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_DictComp(self, node: ast.DictComp) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Await(self, node: ast.Await) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Yield(self, node: ast.Yield) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_YieldFrom(self, node: ast.YieldFrom) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Compare(self, node: ast.Compare) -> Operator:
        """ Compare(expr left, cmpop* ops, expr* comparators) """
        assert len(node.ops) == len(node.comparators) == 1
        op = Operator(node.ops[0].__class__.__dict__["__doc__"].lower())
        self.process_operand(op, node.left, "left")
        self.process_operand(op, node.comparators[0], "comparators0")
        return op

    def visit_Call(self, node: ast.Call) -> Operator:
        """ Call(expr func, expr* args, keyword* keywords) """
        op = Operator("call")
        node_func = node.func
        if isinstance(node_func, ast.Name):
            op.attributes['func'] = node_func.id
        else:
            op.attributes['func'] = str(node_func)
        for i, arg in enumerate(node.args):
            self.process_operand(op, arg, str(i))
        op.attributes["keywords"] = str(node.keywords)
        return op

    def visit_FormattedValue(self, node: ast.FormattedValue) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Constant(self, node: ast.Constant) -> Operator:
        """ Constant(constant value, string? kind) """
        op = Operator("constant")
        op.attributes['kind'] = str(node.kind)
        op.attributes['value'] = str(node.value)
        return op

    def visit_NamedExpr(self, node: ast.NamedExpr) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Attribute(self, node: ast.Attribute) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Subscript(self, node: ast.Subscript) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Starred(self, node: ast.Starred) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Name(self, node: ast.Name) -> ValueId:
        if node.id in self.var_scopes[-1]:
            op = Operator("load")
            op.attributes['name'] = node.id
            op.return_names.append(ValueId(f"%{node.id}_{str(id(op))[-2:]}"))
            self.parent_blocks[-1].append(op)
            return op.return_names[-1]
        else:
            return ValueId(f"%{node.id}")

    def visit_List(self, node: ast.List) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Tuple(self, node: ast.Tuple) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Del(self, node: ast.Del) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Load(self, node: ast.Load) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Store(self, node: ast.Store) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_And(self, node: ast.And) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Or(self, node: ast.Or) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Add(self, node: ast.Add) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_BitAnd(self, node: ast.BitAnd) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_BitOr(self, node: ast.BitOr) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_BitXor(self, node: ast.BitXor) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Div(self, node: ast.Div) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_FloorDiv(self, node: ast.FloorDiv) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_LShift(self, node: ast.LShift) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Mod(self, node: ast.Mod) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Mult(self, node: ast.Mult) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_MatMult(self, node: ast.MatMult) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Pow(self, node: ast.Pow) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_RShift(self, node: ast.RShift) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Sub(self, node: ast.Sub) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Invert(self, node: ast.Invert) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Not(self, node: ast.Not) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_UAdd(self, node: ast.UAdd) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_USub(self, node: ast.USub) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Eq(self, node: ast.Eq) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Gt(self, node: ast.Gt) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_GtE(self, node: ast.GtE) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_In(self, node: ast.In) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Is(self, node: ast.Is) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_IsNot(self, node: ast.IsNot) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Lt(self, node: ast.Lt) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_LtE(self, node: ast.LtE) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_NotEq(self, node: ast.NotEq) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_NotIn(self, node: ast.NotIn) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_comprehension(self, node: ast.comprehension) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_arguments(self, node: ast.arguments) -> List[Tuple[ValueId, SimpleType]]:
        """ arguments(arg* posonlyargs, arg* args, arg? vararg, arg* kwonlyargs,
                      expr* kw_defaults, arg? kwarg, expr* defaults) """
        assert not node.posonlyargs
        assert not node.vararg
        assert not node.kwonlyargs
        assert not node.kw_defaults
        assert not node.kwarg
        assert not node.defaults
        return [self.visit_arg(a) for a in node.args]

    def visit_arg(self, node: ast.arg) -> Tuple[ValueId, SimpleType]:
        assert isinstance(node.annotation, ast.Name)
        return ValueId(f"%{node.arg}"), parse_type(node.annotation)

    def visit_keyword(self, node: ast.keyword) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_alias(self, node: ast.alias) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_withitem(self, node: ast.withitem) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    # visit methods for deprecated nodes
    def visit_ExtSlice(self, node: ast.ExtSlice) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Index(self, node: ast.Index) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Suite(self, node: ast.Suite) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_AugLoad(self, node: ast.AugLoad) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_AugStore(self, node: ast.AugStore) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Param(self, node: ast.Param) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Num(self, node: ast.Num) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Str(self, node: ast.Str) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Bytes(self, node: ast.Bytes) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_NameConstant(self, node: ast.NameConstant) -> Operator:
        raise NotImplementedError(ast.unparse(node))

    def visit_Ellipsis(self, node: Ellipsis) -> Operator:
        raise NotImplementedError(ast.unparse(node))
