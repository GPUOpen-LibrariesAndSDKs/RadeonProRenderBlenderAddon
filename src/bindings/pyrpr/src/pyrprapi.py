#**********************************************************************
# Copyright 2020 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#********************************************************************
import sys
import platform
from pathlib import Path
from itertools import *

bindingsOk = Path("./bindings-ok")

class ConstantDesc:

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def save(self, saver):
        saver['name'] = self.name
        saver['value'] = self.value

    @classmethod
    def load(cls, loader):
        return cls(name=loader['name'], value=loader['value'])


class VarDesc:

    def __init__(self, name, type):
        self.name = name
        self.type = type

    def save(self, saver):
        saver['name'] = self.name
        saver['type'] = self.type

    @classmethod
    def load(cls, loader):
        return cls(name=loader['name'], type=loader['type'])


class ArgDesc(VarDesc):

    def __init__(self, name, type, default):
        self.name = name
        self.type = type
        self.default = default

    def save(self, saver):
        saver['name'] = self.name
        saver['type'] = self.type
        if self.default is not None:
            saver['default'] = self.default

    @classmethod
    def load(cls, loader):
        return cls(name=loader['name'], type=loader['type'], default=loader.get('default'))


class FunctionDesc:

    def __init__(self, name, restype, args, docs=None):
        self.name = name
        self.args = args
        self.restype = restype
        self.docs = docs

    def save(self, saver):
        saver['name'] = self.name
        saver['restype'] = self.restype
        saver.save_array('args', self.args)
        saver['docs'] = self.docs

    @classmethod
    def load(cls, loader):
        return cls(name=loader['name'], restype=loader['restype'],
                   args=[ArgDesc.load(l) for l in loader['args']],
                   docs=loader['docs'])


class TypedefDesc:

    kind = 'typedef'

    def __init__(self, name, type):
        self.name = name
        self.type = type

    def save(self, saver):
        saver['name'] = self.name
        saver['kind'] = 'typedef'
        saver['type'] = self.type

    @classmethod
    def load(cls, loader):
        return cls(name=loader['name'], type=loader['type'])


class StructDesc:

    kind = 'struct'

    def __init__(self, name, fields):
        self.name = name
        self.fields = fields

    def save(self, saver):
        saver['name'] = self.name
        saver['kind'] = 'struct'
        saver.save_array('fields', self.fields)

    @classmethod
    def load(cls, loader):
        return cls(name=loader['name'],
                   fields=[VarDesc.load(l) for l in loader['fields']]
                   )
class ApiDesc:

    def __init__(self):
        self.types = collections.OrderedDict()
        self.constants = collections.OrderedDict()
        self.functions = collections.OrderedDict()


import collections

class Saver(collections.OrderedDict):

    def __init__(self):
        pass

    def save_array(self, key, objects):

        result = []
        for obj in objects:
            s = Saver()
            obj.save(s)
            result.append(s)
        self[key] = result

    def add_record(self, key):
        self[key] = Saver()
        return self[key]

    def update_from_dict(self, d):
        for key, value in d.items():
            value.save(self.add_record(key))


def save(api: ApiDesc, file_name):
    import json

    saver = Saver()

    saver.add_record('constants').update_from_dict(api.constants)
    saver.add_record('types').update_from_dict(api.types)
    saver.add_record('functions').update_from_dict(api.functions)
    print(saver)

    json.dump(saver, open(file_name, 'w'), indent=2)


class Loader:

    def __init__(self, d):
        self.d = d

def load(fpath):
    import json

    api = ApiDesc()

    loader = json.load(open(fpath),
                       object_pairs_hook=collections.OrderedDict) # make sure order is always same

    api.constants = collections.OrderedDict((local_name, ConstantDesc.load(data)) for local_name, data in loader['constants'].items())
    api.types = collections.OrderedDict((local_name, {'typedef': TypedefDesc, 'struct': StructDesc}[data['kind']].load(data) ) for local_name, data in loader['types'].items())
    api.functions = collections.OrderedDict((local_name, FunctionDesc.load(data)) for local_name, data in loader['functions'].items())

    return api


def export(header_file, includes, json_file_name, prefixes, castxml, exclude=None, replace=None):
    import xml.etree.ElementTree
    import subprocess

    if bindingsOk.exists():
         bindingsOk.unlink()

    cmd = [castxml,]
    for inc in includes:
        cmd.extend(['-I', inc])
    cmd.extend(['-std=c++11', '-E', '-dD', '-x' , 'c++', header_file, '-o', 'rprapi.pp'])
    subprocess.check_call(cmd)

    cmd = [castxml,]
    for inc in includes:
        cmd.extend(['-I', inc])
    cmd.extend(['-std=c++11', '--castxml-gccxml', '-x', 'c++', header_file, '-o', 'rprapi.xml'])
    subprocess.check_call(cmd)

    t = xml.etree.ElementTree.parse('rprapi.xml')

    root = t.getroot()

    class Type:

        def __init__(self, name):
            self.name = name
            self.depth = None

        def __repr__(self):
            return self.name

        def get_name_for_typedef(self):
            return self.name

        def get_name_for_var_decl(self):
            return self.name

        def generate_cdecl(self):
            return None

        def generate_desc(self):
            return None

        def calculate_depth(self):
            self.depth = 0


    class Function(Type):

        def __init__(self, name, returns, args):
            super().__init__(name)
            self.returns = returns
            self.args = args

        def __repr__(self):
            return 'function:  '+str(types[self.returns])+self.name+str(self.args)

        def get_name_for_typedef(self):
            assert False

        def get_name_for_var_decl(self):
            assert False

        def generate_cdecl(self):
            desc = self.generate_desc()
            return desc.restype + ' ' + desc.name + '('+', '.join(arg.type+' '+arg.name for arg in desc.args)+');'

        def generate_desc(self):
            return FunctionDesc(self.name,
                                types[self.returns].get_name_for_typedef(),
                                [ArgDesc(arg[0], arg[1].get_name_for_typedef(), arg[2]) for arg in self.args])

        def calculate_depth(self):
            self.depth = 0


    class Typedef(Type):

        def __init__(self, name, typedef_type):
            super().__init__(name)
            self.typedef_type = typedef_type

        def __repr__(self):
            return 'typedef '+repr((self.name, types.get(self.typedef_type, self.typedef_type)))

        def get_name_for_typedef(self):
            return self.name

        def get_name_for_var_decl(self):
            return self.name

        def generate_cdecl(self):
            if not self.depth:
                return None
            desc = self.generate_desc()
            return ' '.join(['typedef', desc.type, desc.name]) + ';'

        def generate_desc(self):
            return TypedefDesc(self.name, types[self.typedef_type].get_name_for_typedef())

        def calculate_depth(self):
            if self.depth is None:
                if self.typedef_type in types:
                    anc = types[self.typedef_type]
                    calculate_depth(anc)
                    self.depth = anc.depth + 1
                else:
                    self.depth = 0

    class Pointer(Type):

        def __init__(self, type):
            super().__init__('~~pointer~~')
            self.pointer_type = type

        def __repr__(self):
            return 'pointer to '+repr(types.get(self.pointer_type, self.pointer_type))

        def get_name_for_typedef(self):
            assert self.pointer_type in types
            return types[self.pointer_type].get_name_for_typedef()+'*'

        def get_name_for_var_decl(self):
            assert self.pointer_type in types
            return types[self.pointer_type].get_name_for_typedef()+'*'

        def generate_cdecl(self):
            # assert self.pointer_type in types, self.pointer_type
            #return 'HELLO-generate_cdecl for' + self.pointer_type
            return None

        def calculate_depth(self):
            if self.depth is None:
                assert self.pointer_type
                if self.pointer_type in types:
                    anc = types[self.pointer_type]
                    calculate_depth(anc)
                    self.depth = anc.depth + 1
                else:
                    self.depth = 0

    class Callback(Type):
        def __init__(self, type):
            super().__init__('~~function~~')
            self.function_type = type

        def __repr__(self):
            return 'pointer to function ' + repr(types.get(self.function_type, self.function_type))

        def get_name_for_typedef(self):
            assert self.function_type in types
            ret_type = types[self.function_type].get_name_for_typedef()
            ret_type = ret_type[:-1]
            return ret_type

        def get_name_for_var_decl(self):
            assert self.function_type in types
            return types[self.function_type].get_name_for_typedef()

        def generate_cdecl(self):
            # assert self.pointer_type in types, self.pointer_type
            # return 'HELLO-generate_cdecl for' + self.pointer_type
            return None

        def calculate_depth(self):
            if self.depth is None:
                assert self.function_type
                if self.function_type in types:
                    anc = types[self.function_type]
                    calculate_depth(anc)
                    self.depth = anc.depth + 1
                else:
                    self.depth = 0

    class CvQualifiedType(Type):

        def __init__(self, type, const):
            assert const
            super().__init__('~~cv-qualified~~')
            self.type = type
            self.const = const

        def __repr__(self):
            return ('const ' if self.const else ' ')+repr(types.get(self.type, self.type))

        def get_name_for_typedef(self):
            assert self.type in types
            return types[self.type].get_name_for_typedef()+' const' if self.const else ''

        def get_name_for_var_decl(self):
            return self.get_name_for_typedef()

        def generate_cdecl(self):
            # assert self.pointer_type in types, self.pointer_type
            #return 'HELLO-generate_cdecl for' + self.pointer_type
            return None

        def calculate_depth(self):
            if self.depth is None:
                assert self.type
                if self.type in types:
                    anc = types[self.type]
                    calculate_depth(anc)
                    self.depth = anc.depth + 1
                else:
                    self.depth = 0


    class Struct(Type):

        def __init__(self, name, fields):
            super().__init__(name)
            self.fields = fields

        def __repr__(self):
            return 'struct:'+str((self.name, [repr(members.get(id, id)) for id in self.fields] ))

        def get_name_for_typedef(self):
            # case for "typedef struct {}* typename;" which cffi can't parse
            return 'struct ' + self.name

        def generate_cdecl(self):

            desc = self.generate_desc()

            lines = []
            lines.append(' '.join(['struct', desc.name, '{']))

            for m in desc.members:
                lines.append('    '+m.type+' '+m.name+' hello;')

            lines.append('};')
            return '\n'.join(lines)

        def generate_desc(self):
            return StructDesc(self.name, [VarDesc(members[field][0], members[field][1].get_name_for_var_decl())
                                          for field in self.fields
                                          if field in members])

        def calculate_depth(self):
            if self.depth is not None:
                return


            for field in self.fields:
                if field in members:
                    f = members[field]
                    calculate_depth(f[1])


            self.depth = 1+max((members[field][1].depth for field in self.fields if field in members), default=-1)

    types = {c.get('id'): Type(c.get('name')) for c in root.findall('FundamentalType')}

    for c in root.findall('FunctionType'):
        for arg in c.findall('Argument'):
            types[c.get('id')] = Callback(arg.get('type'))

    for c in root.findall('PointerType'):
        types[c.get('id')] = Pointer(c.get('type'))

    for c in root.findall('CvQualifiedType'):
        types[c.get('id')] = CvQualifiedType(c.get('type'), eval(c.get('const')))


    for c in root.findall('Struct'):
        name = c.get('name')
        if name.startswith("__"):
            continue
        struct_members = c.get('members')
        types[c.get('id')] = Struct(name, struct_members.split() if struct_members else [])

    for c in root.findall('Typedef'):
        name = c.get('name')
        types[c.get('id')] = Typedef(name, c.get('type'))


    def calculate_depth(t):
        t.calculate_depth()

    members = {}

    for c in root.findall('Field'):
        name = c.get('name')
        type_ = c.get('type')
        if type_ not in types:
            continue
        members[c.get('id')] = (name, types[type_])

    # calculate depths of dependencies on other types
    typedefs_sorted = {}

    for t in types.values():
        calculate_depth(t)
        if t.depth not in typedefs_sorted:
            typedefs_sorted[t.depth] = []
        typedefs_sorted[t.depth].append(t)

    functions = []
    for c in root.findall('Function'):
        name = c.get('name')

        for arg in c.findall('Argument'):
            nname = arg.get('name')
            ttype = arg.get('type')
            typename = types[ttype]

            #FunctionDesc(self.name,
            #             types[self.returns].get_name_for_typedef(),
            #             [ArgDesc(arg[0], arg[1].get_name_for_typedef(), arg[2]) for arg in self.args])

        args = [(arg.get('name'), types[arg.get('type')], arg.get('default')) for arg in c.findall('Argument')]

        functions.append(Function(name, c.get('returns'), args))

    api = ApiDesc()
    for i in sorted(typedefs_sorted.keys()):
        for t in sorted(typedefs_sorted[i], key=lambda t: t.name):
            name = t.name
            for prefix in prefixes['type']:
                # ignore name containing any entry from 'exclude' list
                is_excluded = next((True for e in exclude if e in name), False) if exclude else False
                if name.startswith(prefix) and not is_excluded:
                    local_name = name[len(prefix):]
                    api.types[name] = t.generate_desc()

    for t in sorted(functions, key=lambda t: t.name):
        name = t.name
        for prefix in prefixes['function']:
            # ignore name containing any entry from 'exclude' list
            is_excluded = next((True for e in exclude if e in name), False) if exclude else False
            if name.startswith(prefix) and not is_excluded:
                local_name = name[len(prefix):]
                api.functions[name] = t.generate_desc()


    for line in open('rprapi.pp'):
        if line.startswith('#define'):
            tokens = line.split()
            name = tokens[1]
            # ignore name containing any entry from 'exclude' list
            is_excluded = next((True for e in exclude if e in name), False) if exclude else False
            if 'API_ENTRY' not in name and not is_excluded:
                for prefix in prefixes['constant']:
                    if name.startswith(prefix):
                        # replace some bug-producing defines by predefined value
                        if replace and name in replace:
                            value = replace[name]
                        else:
                            value = ' '.join(tokens[2:])

                            # if define points at other prefixed define correct value name by removing prefix
                            value_prefix = next(
                                (p for p in prefixes['constant'] if value.startswith(p)),
                                None)
                            if value_prefix:
                                value = value[len(value_prefix):]

                            local_name = name[len(prefix):]

                        api.constants[name] = ConstantDesc(name, value)

    def parse_multiline_comment(line, lines):
        for line in chain([line], lines):
            yield line
            if '*/' in line:
                return

    def clean_comment_line(line):

        while line and (line[0] in ['\\', '*', '/', ' ', '\t']):
            line = line[1:]

        return line.lstrip()

    def extract_function_comments(lines):
        comment = ''

        for line in lines:
            #print('>>>', line)

            if line.startswith('/*'):
                comment = list(parse_multiline_comment(line, lines))
                continue

            if 'frContextFlushImageCache' in line:
                continue

            if line.startswith('extern RPR_API_ENTRY'):
                # get all lined of function declaration(up to closing bracket)
                l = line
                while ')' not in l:
                    l = next(lines)
                    line += l

                line_cleaned = line.replace('extern RPR_API_ENTRY', '').lstrip()
                restype_and_name, args_rest = line_cleaned.split('(')

                restype, name = restype_and_name.split()

                yield 'function', (name, (restype, tuple(arg.strip() for arg in args_rest.split(')')[0].split(',')), [line_cleaned, comment]))


    for type, (name, sig) in extract_function_comments(open(header_file)):
        if name.startswith('rpr'):
            local_name = name[len('rpr'):]
            api.functions[name].docs = sig[2]

    save(api,json_file_name)

    # If we got this far the current binding should have generated
    bindingsOk.write_text("ok")


def eval_constant(s):
    if s.endswith(('U', 'u')):
        s = s[:-1]

    try:
        return eval(s)
    
    except NameError:
        return s


def get_rpr_sdk(base=Path()):
    p = base / ".sdk/rpr"
    return {
        'inc': p / "inc",
        'bin': p / "bin",
        'lib': p / "lib" if platform.system() == 'Windows' else None
    }


def get_rif_sdk(base=Path()):
    p = base / ".sdk/rif"
    return {
        'inc': p / "inc",
        'bin': p / "bin",
        'lib': p / "lib" if platform.system() == 'Windows' else None
    }


if __name__=='__main__':
    #change paths according to your developer environment:
    #castxml = r'C:\Development\tools\castxml\bin\castxml'

    castxml = sys.argv[1]

    rpr_sdk = get_rpr_sdk()
    rif_sdk = get_rif_sdk()

    # RPR
    rpr_wrap_h = 'src/bindings/pyrpr/rprwrap.h'
    rpr_includes = [str(rpr_sdk['inc'])]
    rpr_wrap_json = 'src/bindings/pyrpr/src/pyrprwrapapi.json'

    # ImageProcessing
    rif_wrap_h = 'src/bindings/pyrpr/imagefilterswrap.h'
    rif_wrap_json = 'src/bindings/pyrpr/src/pyrprimagefiltersapi.json'
    rif_includes = [*rpr_includes, str(rif_sdk['inc'])]

    export(
        rpr_wrap_h, rpr_includes, rpr_wrap_json,
        {
            'type': ['rpr_', '_rpr'],
            'function': ['rpr',],
            'constant': ['RPR_',]
        },
        castxml,
        exclude=['RPR_CONTEXT_FLUSH_FRAMEBUFFERS_FUNC_NAME',
                 'RPR_SHAPE_SET_LIGHTMAP_CHART_INDEX_FUNC_NAME',
                 'RPR_MESH_UPDATE_FUNC_NAME',
                 'RPR_SHAPE_SET_TRANSFORM_BATCH_FUNC_NAME',
                 'rprDirectionalLightSetRasterShadowSplits',
                 'rprContextCreateMeshInstanceWithUniqueAttributes',
                 'RPR_CONTEXT_CREATE_MESH_EDITABLE_FUNC_NAME',
                 'rprContextCreateCompressedImage_func',
                 'rpr_compressed_format',
                 'rpr_comressed_image_desc',
                 'RPR_CONTEXT_CREATE_COMPRESSED_IMAGE',
                 'rpr_framebuffer_type',
                 'RPR_UV_CAMERA_SET_CHART_INDEX_FUNC_NAME',
                 'RPR_CONTEXT_CREATE_FRAMEBUFFER_TYPED_FUNC_NAME',
                 'RPR_MATERIAL_SET_INPUT_BY_S_KEY_FUNC_NAME',
                 'RPR_MATERIALX_SET_FILE_FUNC_NAME',
                 'RPR_MATERIALX_SET_FILE_AS_BUFFER_FUNC_NAME',
                 'rpr_vector_component_type',
                 'rpr_format_ext',
                 'RPR_CONTEXT_CREATE_IMAGE_FROM_EXTERNAL_HANDLE',
                 'rprGetSupportedDevices',
                 ]
    )

    export(
        rif_wrap_h, rif_includes, rif_wrap_json,
        {
            'type': ['rif_', '_rif'],
            'function': ['rif'],
            'constant': ['RIF_', 'VERSION_', 'COMMIT_'],
        },
        castxml,
        exclude=['RIF_DEPRECATED', 'RIF_MAKE_VERSION', 'RIF_API_VERSION', 'VERSION_BUILD',
                 'RIF_STRINGIFY2(s)', 'RIF_STRINGIFY(s)',
                 'rif_logger_desc', 'rifLoggerAttach', 'rifGetModelMemorySize']
    )

    # export(rpr_header_gltf, includes_gltf, json_file_name_gltf,
    #        {
    #            'type': ['rprgltf_'],
    #            'function': ['rprExport', 'rprImport', 'rprGLTF'],
    #            'constant': []
    #        },
    #        castxml)
