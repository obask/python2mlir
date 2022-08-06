import ast
from pprint import pprint

BAD_TOKENS = {'lineno', 'col_offset', 'end_lineno', 'end_col_offset', 'ctx'}


def transform(node):
    if hasattr(node, '__dict__'):
        tmp = dict((k, transform(v)) for k, v in node.__dict__.items() if k not in BAD_TOKENS)
        tmp['_t'] = type(node).__name__
        return tmp
    elif type(node) is list:
        return [transform(it) for it in node]
    else:
        return node


CODE = """

def fn():
    x = 0
    temp = f1(g1(x))
    # while temp > 0:
    #    digit = temp * 10
    #    sum += digit * 3
    #    temp //= 10
    # if 123 == sum:
    #    print(num,"is an Armstrong number")
    # else:
    #    print(num,"is not an Armstrong number")
"""


def main():
    tree = ast.parse(CODE)
    json_x = transform(tree)
    pprint(json_x, compact=True)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
