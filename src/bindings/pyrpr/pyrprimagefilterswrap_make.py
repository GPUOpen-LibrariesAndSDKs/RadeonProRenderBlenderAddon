import sys

sys.path.append('src')

import pyrprapi

api_desc_fpath = sys.argv[1]


def clean_comment_line(line):
    while line and (line[0] in ['\\', '*', '/', ' ', '\t']):
        line = line[1:]

    return line.lstrip()


api = pyrprapi.load(api_desc_fpath)


def format_arg_decl(arg, default):
    if default is None:
        return arg
    return arg + '=' + ({'false': 'False', 'true': 'True'}.get(default, default))


def print_function_header(name, args_names, args_defaults, doc):
    print('def', name + '(' + ', '.join(format_arg_decl(a, d) for a, d, in zip(args_names, args_defaults)) + '):')
    if doc:
        c_decl, comment = doc
        print('    """ C/C++:', c_decl)
        print('    '.join(clean_comment_line(line) for line in comment))
        print('    """')
        print('    ')


print()
print()

constants_names = []

for name, c in api.constants.items():
    prefix = 'RIF_'
    if name.startswith(prefix):
        name = name[len(prefix):]

    print('{} = {}'.format(name, pyrprapi.eval_constant(c.value)))
    constants_names.append(name)

print('_constants_names =', repr(constants_names))

types_names = []
for name, t in api.types.items():
    if 'struct' == t.kind:
        pass
    else:
        pass
    for prefix in ['_rif', 'rif_', '_rif', 'rif_']:
        if name.startswith(prefix):
            short_name = name[len(prefix):]
            for n in [short_name]:
                types_names.append(n)

print('_types_names =', repr(types_names))

functions_names = []

for name, t in api.functions.items():
    args_names = []
    args_defaults = []
    replace_args = []

    for arg_i, arg in enumerate(t.args):

        argtype = arg.type
        argname = arg.name
        argdefault = arg.default

        args_names.append(argname)
        args_defaults.append(argdefault)

        replace_arg = False
        if all((prefix not in name) for prefix in 'InstanceGetBaseShape ObjectDelete ObjectSetName RegisterPlugin'.split()):
            if argtype.split('*')[0].strip() in ['rif_context', 'rif_command_queue', 'rif_image_filter', 'rif_image']:
                replace_arg = 'value'
                if '*' in argtype:
                    replace_arg = 'pointer'

        replace_args.append(replace_arg)


    def get_arg(arg, replaced):
        if not replaced:
            return arg
        if 'value' == replaced:
            return '{0}._get_handle() if {0} else ffi.NULL'.format(arg)
        if 'pointer' == replaced:
            return '{0}._handle_ptr if {0} else ffi.NULL'.format(arg)


    prefix = 'rif'
    if name.startswith(prefix):
        # create functions that omit prefix(for new way to call api in python)
        short_name = name[len(prefix):]
        names = [short_name]

        for n in names:
            functions_names.append(n)
            print_function_header(n, args_names, args_defaults, t.docs if t.docs else api.functions[name].docs)
            if any(replace_args):
                print('    return lib.' + name + '(' + ', '.join(
                    get_arg(arg, replaced) for arg, replaced in zip(args_names, replace_args)) + ')')
                print()
            else:
                # functions with dummy wrapper(so that we have intellisense
                print(n, file=sys.stderr)
                print('    return lib.' + name + '(' + ', '.join(args_names) + ')')
                print()

print('_functions_names =', repr(functions_names))
