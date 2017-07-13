#!python3

import sys
import os

from pathlib import Path

rprsdk_path = Path('../../../ThirdParty/RadeonProRender SDK/Win')

rprsdk_bin_path = rprsdk_path / 'bin'

sys.path.append('.build')
sys.path.append('src')
import pyrpr

pyrpr.lib_wrapped_log_calls = True


def log(*args):
    # print(*args)
    sys.stdout.flush()


pyrpr.init(log, rprsdk_bin_path=rprsdk_bin_path)
ffi = pyrpr.ffi


def ensure_core_cache_folder():
    path = str(Path(__file__).parent / '.core_cache' / hex(pyrpr.API_VERSION))

    if not os.path.isdir(path):
        os.makedirs(path)
    return path


if not os.path.isdir(".rprtrace"):
    os.mkdir(".rprtrace")
pyrpr.ContextSetParameterString(ffi.NULL, b"tracingfolder", os.path.abspath(".rprtrace").encode('latin1'));
pyrpr.ContextSetParameter1u(ffi.NULL, b"tracing", True);

tahoePluginID = pyrpr.RegisterPlugin(str(rprsdk_bin_path / "Tahoe64.dll").encode('utf8'))

assert -1 != tahoePluginID

plugins = [tahoePluginID]
pluginCount = len(plugins)

context = pyrpr.Context([tahoePluginID], pyrpr.CREATION_FLAGS_ENABLE_GPU0,
                        cache_path=str(ensure_core_cache_folder().encode('latin1')))

print('API_VERSION', hex(pyrpr.API_VERSION))

print('Context')

print('-' * 80)

contextParameterCountPtr = ffi.new('size_t *', 0)
pyrpr.ContextGetInfo(context, pyrpr.CONTEXT_PARAMETER_COUNT, ffi.sizeof('size_t'),
                     contextParameterCountPtr, ffi.NULL)

contextParameterCount = contextParameterCountPtr[0]
assert 46 == contextParameterCount, contextParameterCount

types = set()


def enumerate_context_params():
    for i in range(contextParameterCount):
        sizePtr = ffi.new('size_t *', 0)
        pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_NAME_STRING, 0, ffi.NULL, sizePtr)
        size = sizePtr[0]

        namePtr = ffi.new('char[]', size)
        pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_NAME_STRING, size, namePtr, ffi.NULL)
        name = ffi.string(namePtr)

        sizePtr = ffi.new('size_t *', 0)
        pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_DESCRIPTION, 0, ffi.NULL, sizePtr)
        size = sizePtr[0]

        descPtr = ffi.new('char[]', size)
        pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_DESCRIPTION, size, descPtr, ffi.NULL)
        desc = ffi.string(descPtr)

        typePtr = ffi.new('rpr_int*')
        pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_TYPE, ffi.sizeof('rpr_int'), typePtr,
                                      ffi.NULL)
        type = typePtr[0]
        types.add(type)

        # UINT: 8 FLOAT: 1 FLOAT4: 4 STRING: 6

        xxx = {
            pyrpr.PARAMETER_TYPE_UINT: ('rpr_uint*', 1),
            pyrpr.PARAMETER_TYPE_FLOAT: ('rpr_float*', 1),
            pyrpr.PARAMETER_TYPE_FLOAT4: ('rpr_float*', 4),
            pyrpr.PARAMETER_TYPE_STRING: ('char*', None)
        }

        core_type_name, core_type_count = xxx[type]

        try:
            log(name, type)

            sys.stdout.flush()
            sizePtr = ffi.new('size_t *', 0)
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_VALUE, 0, ffi.NULL, sizePtr)
            size = sizePtr[0]
            log(size)
            sys.stdout.flush()
            assert size, i

            valuePtr = ffi.cast(core_type_name, ffi.new('char[]', size))
            pyrpr.ContextGetParameterInfo(context, i, pyrpr.PARAMETER_VALUE,
                                          size, valuePtr, ffi.NULL)
            if pyrpr.PARAMETER_TYPE_STRING == type:
                value = repr(ffi.string(valuePtr).decode('ascii'))
            elif core_type_count not in (1, None):
                value = [valuePtr[j] for j in range(core_type_count)]
            else:
                value = valuePtr[0]
        except pyrpr.CoreError:
            raise
            value = '<UNSUPPORTED>'
        log(name, value, desc)
        yield name, value, desc


for name, value, desc in sorted(enumerate_context_params()):
    print("'%s', def: %s, '%s'" % (name.decode('latin1'), value, desc.decode('latin1')))

print('-' * 80)

scene = pyrpr.Scene(context)
pyrpr.ContextSetScene(context, scene)

matsys = pyrpr.MaterialSystem()
pyrpr.ContextCreateMaterialSystem(context, 0, matsys)

# ********************* list material nodes and input names

not_material_node_names = ['MATERIAL_NODE_TYPE',
                           'MATERIAL_NODE_SYSTEM',
                           'MATERIAL_NODE_INPUT_COUNT',
                           'MATERIAL_NODE_INPUT_',
                           'MATERIAL_NODE_OP_',
                           'MATERIAL_NODE_LOOKUP_',
                           # 'MATERIAL_NODE_VOLUME',  # this just doesn't work in 1.230
                           'MATERIAL_NODE_CONSTANT_TEXTURE',  # this just doesn't work in 1.234
                           ]

parameter_prefix = 'PARAMETER_TYPE_'

parameter_type_to_string = {
    getattr(pyrpr, name): name.replace(parameter_prefix, '').capitalize() for name in dir(pyrpr)
    if name.startswith(parameter_prefix)}

print('Material nodes')
print('-' * 80)
for name in sorted(dir(pyrpr)):
    if name.startswith('MATERIAL_NODE_'):
        if name not in ['MATERIAL_NODE_INPUT_LOOKUP']:
            if [prefix for prefix in not_material_node_names if name.startswith(prefix)]:
                continue

        material_name = getattr(pyrpr, name)
        print(name, material_name)

        shader = pyrpr.MaterialNode()
        pyrpr.MaterialSystemCreateNode(matsys, material_name, shader)

        input_count_ptr = ffi.new('size_t*')
        pyrpr.MaterialNodeGetInfo(shader, pyrpr.MATERIAL_NODE_INPUT_COUNT, ffi.sizeof('size_t'), input_count_ptr,
                                  ffi.NULL)

        for i in range(input_count_ptr[0]):
            sizePtr = ffi.new('size_t *', 0)
            pyrpr.MaterialNodeGetInputInfo(shader, i, pyrpr.MATERIAL_NODE_INPUT_NAME_STRING, 0, ffi.NULL, sizePtr)
            size = sizePtr[0]

            namePtr = ffi.new('char[]', size)
            pyrpr.MaterialNodeGetInputInfo(shader, i, pyrpr.MATERIAL_NODE_INPUT_NAME_STRING, size, namePtr, ffi.NULL)
            name = ffi.string(namePtr).decode('ascii')

            print('///', name, end=' ')

            typePtr = ffi.new('size_t*', size)
            pyrpr.MaterialNodeGetInputInfo(shader, i, pyrpr.MATERIAL_NODE_INPUT_TYPE, ffi.sizeof('size_t'), typePtr,
                                           ffi.NULL)
            typ = typePtr[0]

            print(parameter_type_to_string[int(typ)])

print('-' * 80)
