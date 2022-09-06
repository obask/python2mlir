import ast
from dataclasses import dataclass, field
from pprint import pprint

import mlir
from mlir.printer import DefaultPrinter
from visitor import PyVisitor

BAD_TOKENS = {'lineno', 'col_offset', 'end_lineno', 'end_col_offset', 'ctx'}


@dataclass
class Visitor:
    insertion_point: list[mlir.Operator] = field(default_factory=list)

    def visit(self, node):
        if hasattr(node, '__dict__'):
            tmp = dict((k, self.visit(v)) for k, v in node.__dict__.items() if k not in BAD_TOKENS)
            tmp['_t'] = type(node).__name__
            return tmp
        elif type(node) is list:
            return [self.visit(it) for it in node]
        else:
            return node


CODE = """

def compute_hcf(x: int, y: int) -> List[int]:
    # if x > y:
    #     smaller = y
    # else:
    #     smaller = x
    # for i in range(1, smaller+1):
    #     if((x % i == 0) and (y % i == 0)):
    #         hcf = i 
    a: List[int] = x + y
    return a
"""


def main():
    tree = ast.parse(CODE)
    # json_x = Visitor().visit(tree)
    module_op = PyVisitor().visit_Module(tree)
    pprint(module_op, compact=True)

    sb = DefaultPrinter().render_operator(module_op)
    print("".join(sb))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
