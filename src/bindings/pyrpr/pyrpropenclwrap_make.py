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

constants_names = []

def get_constant_value(c):
    if c.value.endswith('U'):
        return c.value[:-1]
    return c.value

for name, c in api.constants.items():
    prefix = 'RPR_CL_'
    if name.startswith(prefix):
        short_name = name[len(prefix):]

        for n in [short_name]:
            print('{} = {}'.format(n, get_constant_value(c) ))
            constants_names.append(n)
print('_constants_names =', repr(constants_names))

types_names = []
for name, t in api.types.items():
    if 'struct' == t.kind:
        pass
    else:
        pass
    for prefix in ['_rpr_cl', 'rpr_cl_']:
        if name.startswith(prefix):
            short_name = name[len(prefix):]
            for n in [short_name]:
                # print('{} = {}'.format(n, name))
                types_names.append(n)

print('_types_names =', repr(types_names))