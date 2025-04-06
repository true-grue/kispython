import ast


def make_object(ty, val):
    return {'__class__': ty, 'value': val}


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
            return make_object(Int, value)
        case ast.Call(ast.Name(name), args):
            obj = load_name(frame, name)
            ty = obj['__class__']
            args = (exec_expr(frame, arg) for arg in args)
            return ty['__call__'](frame, obj, *args)
        case _:
            raise SyntaxError


def exec_block(frame, tree):
    for stmt in tree:
        exec_stmt(frame, stmt)


def exec_stmt(frame, tree):
    match tree:
        case ast.FunctionDef(name, args, body):
            func = make_object(Function, (args.args, body))
            store_name(frame, name, func)
        case ast.Assign([ast.Name(name)], expr):
            store_name(frame, name, exec_expr(frame, expr))
        case ast.Expr(expr):
            exec_expr(frame, expr)
        case _:
            raise SyntaxError


def exec_module(frame, tree):
    match tree:
        case ast.Module(block):
            new_frame = frame | {'locals': frame['globals']}
            exec_block(new_frame, block)
        case _:
            raise SyntaxError


def call_func(frame, obj, *args):
    params, body = obj['value']
    locs = {p.arg: a for p, a in zip(params, args)}
    exec_block(frame | {'locals': locs}, body)


def call_builtin(frame, obj, *args):
    return obj['value'](*args)


Type = make_object(None, '__class__')
Type['__class__'] = Type
Int = make_object(Type, 'int')
Str = make_object(Type, 'str')


Function = {
    '__call__': call_func,
    '__name__': make_object(Str, 'function')
}


Builtin = {
    '__call__': call_builtin,
    '__name__': make_object(Str, 'builtin_function_or_method')
}


def builtin_type(obj):
    return obj['__class__']['__name__']


def builtin_print(*args):
    print(*(arg['value'] for arg in args))


builtins = {
    'type': make_object(Builtin, builtin_type),
    'print': make_object(Builtin, builtin_print)
}


src = '''
G = 1
def f(a):
    G = 2
    print(G, a)

f(1)
f(2)
print(G)
print(type(f))
'''

frame = {'builtins': builtins, 'globals': {}}
exec_module(frame, ast.parse(src))
