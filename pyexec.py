import ast


def PyObject(ty, val):
    return {'type': ty, 'value': val}


Type = PyObject(None, 'type')
Type['type'] = Type
Int = PyObject(Type, 'int')
Builtin = PyObject(Type, 'builtin_function_or_method')


def load_name(frame, name):
    if name in frame['locals']:
        return frame['locals'][name]
    if name in frame['globals']:
        return frame['globals'][name]
    if name in frame['builtins']:
        return frame['builtins'][name]
    raise NameError(name)


def store_name(frame, name, value):
    frame['locals'][name] = value


def exec_expr(frame, tree):
    match tree:
        case ast.Name(name):
            return load_name(frame, name)
        case ast.Constant(int(value)):
            return PyObject(Int, value)
        case ast.Call(ast.Name(name), [arg]):
            func = load_name(frame, name)['value']
            return func(exec_expr(frame, arg))
        case _:
            raise SyntaxError


def exec_stmt(frame, tree):
    match tree:
        case ast.Assign([name], expr):
            store_name(frame, name.id, exec_expr(frame, expr))
        case ast.Expr(expr):
            exec_expr(frame, expr)
        case _:
            raise SyntaxError


def exec_block(frame, tree):
    for stmt in tree:
        exec_stmt(frame, stmt)


def exec_module(frame, tree):
    match tree:
        case ast.Module(block):
            exec_block(frame, block)
        case _:
            raise SyntaxError


def print_func(obj):
    print(obj['value'])


def type_func(obj):
    return obj['type']


builtins = {
    'print': PyObject(Builtin, print_func),
    'type': PyObject(Builtin, type_func)
}

globs = {}

Frame = {
    'locals': globs,
    'globals': globs,
    'builtins': builtins
}

src = '''
x = 42
print(type(x))
print(print)
'''

exec_module(Frame, ast.parse(src))
