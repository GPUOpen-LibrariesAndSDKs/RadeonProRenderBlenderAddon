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

    if doc is None:
        return

    c_decl, comment = doc
    print('    """ C/C++:', c_decl)
    print('    '.join(clean_comment_line(line) for line in comment))
    print('    """')
    print('    ')


print()
print()

constants_names = []

for name, c in api.constants.items():
    prefix = 'RPR_'
    if name.startswith(prefix):
        short_name = name[len(prefix):]

        for n in [short_name]:
            print('{} = {}'.format(n, c.value))
            constants_names.append(n)
print('_constants_names =', repr(constants_names))

types_names = []
for name, t in api.types.items():
    if 'struct' == t.kind:
        pass
    else:
        pass
    for prefix in ['_rpr', 'rpr_']:
        if name.startswith(prefix):
            short_name = name[len(prefix):]
            for n in [short_name]:
                # print('{} = {}'.format(n, name))
                types_names.append(n)

print('_types_names =', repr(types_names))

functions_names = []

for name, t in api.functions.items():
    # print(name, [(arg.name, arg.type) for arg in t.args])
    # print(t.restype, name, '('+', '.join(arg.type+' '+arg.name for arg in t.args)+');', file=f)

    args_names = []
    args_defaults = []
    replace_args = []

    for arg_i, arg in enumerate(t.args):

        argtype = arg.type
        # argname = arg_tokens[-1].strip() if 1<len(arg_tokens) else 'arg'+str(arg_i)
        argname = arg.name
        argdefault = arg.default

        args_names.append(argname)
        args_defaults.append(argdefault)

        replace_arg = False
        if any(name.startswith(prefix) for prefix in ['rprCreateContext', 'rprContext', 'rprFrameBuffer',
                                                      'rprComposite', 'rprScene',
                                                      'rprObject', 'rprShape', 'rprCamera', 'rprMesh',
                                                      'rprMaterialSystem', 'rprMaterialNode',
                                                      'rprLight', 'rprPointLight', 'rprSpotLight',
                                                      'rprDirectionalLight',
                                                      'rprEnvironmentLight', 'rprSkyLight',
                                                      'rprPostEffect',
                                                      'rprIESLight',
                                                      'rprImage',
                                                      'rprHeteroVolume', 'rprCurve',
                                                      'rprBuffer']):

            if argtype.split('*')[0].strip() in ['rpr_context', 'rpr_framebuffer', 'rpr_composite', 'rpr_scene',
                                                 'rpr_shape', 'rpr_camera',
                                                 'rpr_material_system', 'rpr_material_node',
                                                 'rpr_light',
                                                 'rpr_post_effect',
                                                 'rpr_image',
                                                 'rpr_hetero_volume', 'rpr_curve',
                                                 'rpr_buffer']:
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


    prefix = 'rpr'
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
