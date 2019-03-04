# Radeon ProRender Blender Addon

### Build Requirements

2.78c
=====
- Blender 2.78c
- Python 3.5.2(Blender 2.78c uses one) x64(for Core) - all code, addon and misc tested with python3
- python-cffi. e.g. following works for me on windows - `py -m pip install cffi`
- Visual Studio 2015 SP3 or Visual Studio 2017 (15.6.7) with SDK 8.1 and 2015.3 v140 toolset installed
- cmake 3.x

2.80
====
- Blender 2.80
- Python 3.7.1(Blender 2.80 uses 3.7.0) x64(for Core) - all code, addon and misc tested with python3
- python-cffi. e.g. following works for me on windows - `py -m pip install cffi`
- Visual Studio 2015 SP3 or Visual Studio 2017 (15.6.7) with SDK 8.1 and 2015.3 v140 toolset installed
- cmake 3.x

Note that the .sln provided is for easy editing and searching of files on Windows.  The blender
code builds on the command line rather than in the solution file.  Visual Studio does provided
support for debugging Python when you attach to a process.

### Software, required for development - to run tests and more:

- pytest - `py -m pip install pytest`
- imageio - `py -m pip install imageio`
- numpy - `py -m pip install numpy`
- pyopengl - `py -3 -m pip install pyopengl`
- pypiwin32 - `py -3 -m pip install pypiwin32`

### ThirdParty libraries

External dependencies must be included in the repository's ThirdParty directory. Please check the README in the ThirdParty directory to see  how to acquire the required libraries.

## Developing

### Coding Conventions

Aim is to conform to [pep8](https://www.python.org/dev/peps/pep-0008/). 
At minimum it's 4 spaces for indentation, sources are utf-8, there's .gitconfig in the root of the project - please set you editor to use it(for most simplicity). E.g. PyCharm(recommended!) default setting are fine and seems that it also picks up .editorconfig automatically also, Tortoise Merge has a checkbox 'Enable EditorConfig', for Visual Studio there's [EditorConfig extension](https://visualstudiogallery.msdn.microsoft.com/c8bccfe2-650c-4b42-bc5c-845e21f96328)

Git - we try to avoid merge commits, easiest way to do it:

`git config [--global] merge.ff only` # this one rejects merges that would result in merge commit
 
`git config [--global] pull.rebase true` # converts pull to do, essentially, fetch&rebase 

Also, make more meaningful commits(one commit per feature) the easy way: 

`git merge <branch> --squash` # this will create a single change set from multiple commits coming from <branch>

### Recommended software

- epydoc - enable PyCharm to parse Core's documentation. Use `py -m pip install epydoc` with your selected python interpreter or install it from PyCharm 
- PyCharm Community Edition - very recommended, possible to enable intellisense(limited) for Blender code and for RPR Core
- Visual Studio - has a very nice python extension, possible to enable intellisense for Blender and for RPR Core, provides remote debugging in Blender

## Build and Test

run `build.py` to build and `test.py` to test. Tests pass on Windows. Please run tests regularly! They take about 10 min - so should be fine to run a couple of times a day.

### Updating RPR to new version

See src/bindings/pyrpr/readme.txt

## Run Addon while developing it(without real installation)

example is here - run_blender_with_rpr.cmd

### Debugging

#### log
 using python's 'logging' module underneath, rprblender.logging has functions similar to logging(but different, probably not good)
e.g. `logging.debug(*argv, tag)` where argv is what is printed(same as with print) and tag is string suffix for logger name, for filtering
so that `logging.limit_log(name, level_show_always)` will allow to filter out what doesn't start with `name`(expect levels equal or above `level_show_always`)

 configdev.py(loaded very early) can be used to include code like `limit_log` to configure your session

    from . import logging
    logging.limit_log('render.camera', level_show_always=logging.INFO)
    
    from . import config
    config.pyrpr_log_calls = True #  log all Core function calls to console, can be VERY useful

- Visual Studio has really nice(and working) mixed(python and C stack) debugging - recommended! 
- Blender debug - it's easiest to [build Blender](https://wiki.blender.org/index.php/Dev:Doc/Building_Blender/Windows/msvc/CMake) in Release or RelWithDebInfo(and add ``#pragma optimize( "", off )``) 
- Debug in PyCharm - `import pydevd; pydevd.settrace('localhost', port=52128, stdoutToServer=True, stderrToServer=True, suspend=False)`

## Making a new release

- run `build_installer.py <build_folder>`. Where `build_folder` is some separate location - it will clone needed repos(if not already), reset then to needed branch and build installer. Byt default it builds windows installer on master.  
- tag the commit in the build folder's ProRenderBlenderPlugin `git tag builds/x.y.zz`
- push the tag `git push --tags` 
- increase version in `src/rprblender/__init__.py`

## PyCharm

### Blender api intellisense support

Get [pycharm-blender](https://github.com/mutantbob/pycharm-blender). See instructions on the github page or, in short, 
run `pypredef_gen.py` from Blender itself or using command line, e.g. `blender --python pypredef_gen.py`,
add "pypredef" folder path that this script creates to you PyCharm Interpreter paths, find paths settings under `File | Settings(or Default Settings) | Project Interpreter`
 
Increase max file size for Pycharm intellisence(bpy.py generated is huge), go to `Help | Edit Custom VM Options` and add the following line:

  -Didea.max.intellisense.filesize=5000000

Restart PyCharm

## Visual Studio

### Create and configure RPRBlender python project 

Install python extension in Visual Studio

Create new project from existing python code: Menu -> File -> New -> Project -> Python tab -> From Existing Python Code

Add following Search Paths to project:
  - rprblender\support
  - C:\Program Files\Blender Foundation\Blender\2.79\scripts\modules   # path where to Blender's modules
  - <path to "PyCharm->Blender api intellisense support">

### Configure VS remote debugger to Blender

#### Install Blender-VScode-Debugger addon

Get Blender-VScode-Debugger plugin for Blender from https://github.com/Barbarbarbarian/Blender-VScode-Debugger

Install plugin Blender_VScode_Debugger.py in Blender: Menu -> File -> User Preferences -> Click "Install Add-on from file" -> Select Blender_VScode_Debugger.py -> Click "Install Add-on from file". New adddon "Development: Debugger for Visual Code" should be appeared

Enable "Development: Debugger for Visual Code" addon. Select "Path to PTVSD module": C:\Program Files (x86)\Microsoft Visual Studio 14.0\Common7\IDE\Extensions\Microsoft\Python Tools for Visual Studio\2.2\

Click "Save User Settings"

#### Attach VS remote debugger to Blender

In Blender: press <Space> -> in appeared dialog type "debug" -> select "Connect to Visual Studio Code Debugger"

In VS: Menu -> Debug -> Attach To Process -> select Transport "Python remote (ptvsd)" -> type in Qualifier "my_secret@localhost:3000" -> click Refresh: process Blender.exe "tcp://localhost:3000" should be appeared -> select process -> click Attach

Remote debugging connection established.

### Making material nodes

Material nodes consist of two parts: 

- Blender UI/Data component(essentially class inherited from `bpy.types.Node`). Definitions located in `src/rprblender/editor_nodes.py`. And added to Blender Node Editor menu in `src/rprblender/nodes.py`
- Part that converts those Blender nodes to Core - these are in `src/rprblender/core/nodes.py`, see class Material there and `parse_...` methods

Conventions _evolving, far from all the code is complying with these, but we'd love to have it eventually_ 

- Nodes are divided into two kinds 'shader' and 'value'. `RPRShaderNode_<node_type>`, `RPRValueNode_<node_type>`. Shaders are nodes which output can go to Output node or input to Blend shader(the only thing that can combine other shaders)
- `bl_idname` formed like this `'rpr_<category>_node_<node_type>'` - `<category>` is where we want to see our node in the ui, mainly, `<node_type>` is lowercase (meaningful)part of the Core node name. E.g. `rpr_texture_node_noise2d`, `rpr_input_node_lookup` - for `FR_MATERIAL_NODE_NOISE2D_TEXTURE` and `FR_MATERIAL_NODE_INPUT_LOOKUP`, located in `Texture` and `Input` submenus of Node Editor's Add menu. Corresponding `parse_..` methods should be called in similar fashion - e.g. `parse_input_node_lookup`. Same with test methods. **THEREFORE, searching for, say, `input_node_lookup` should discover ALL the places where this node is used and all that is needed to implement a similar node**
- `bl_label` - `'RPR <Node_type>'`, e.g. `'RPR Lookup'`
- Output sockets for nodes - every 'value'(i.e. non-shader) node has `value_out = 'Out'`, and 'shaders' `shader_out = 'Shader'`.
- Input sockets are also has an alias in the Node class, like `color_in = 'Diffuse Color'` on Diffuse material. This can be referenced as `self.color_in` withing the `RPRShaderNode_Diffuse` class methods or `RPRSahderNode_Diffuse.color_in` outside(e.g. tests)  

Tests 
 
- At least one test per *Node*. Right now we are aiming to have at least one test that executes node configuring and parsing code and verifies rendered image. All those material tests are located now in `src/rprblender/render_test.py`. E.g. see `test_material_lookup` there.  
- Test code for a node is essentially setting up material shader graph and checking for render output comparing it with specified *expected* image.
 - all render(and some more) tests are run with `tests\blender_tests\run_all_tests.py` script, when a image-comparison fails it creates two output files - `actual.png` and `expected.png` in a subfolder of `failures_last` named after failed test. When an `expected` image is not found(as on the first run of a new test) - only `actual.png` is written to disk, converting it to .png might be used as 'expected' image, if it looks fine) If it's copied to `src/rprblender/testdata/render/...` providing a name used in test - it will be used as a baseline on the next test run. Also `actual_hdr.list` is saved  -  it's actual hdr(unlike clamped/converted in `.png`) pixels of the rendered image. Use `tests\blender_tests\analyze_failure.py` to check them for low/upper bounds.   
 - single test can be run(running all the test takes some time) with the folliwing command, as example:
   `tests\blender_tests\run_all_tests.py src/rprblender/render_test.py::test_material_diffuse_image_map` (that is `'<test_runner> <test file>::<test_name>'`) 
   or `tests\blender_tests\run_all_tests.py src/rprblender -- -k test_material` - runs all tests under `src/rprblender` that contain `test_material` 
 
 - might be **very** useful - adding `--keep-blender-running` to test command will not close Blender(as it does by default) - so it will be possible to inspect created Node graph and experiment with rendering it etc.
     
Example(full test code)

    def test_material_lookup(render_image_check_fixture, material_setup):
    
        with render_image_check_fixture.set_expected('material_lookup_expected.png'):
            # generate simple uvs
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.uv.unwrap()
            bpy.ops.object.mode_set(mode='OBJECT')
    
            tree = material_setup.create_default_node_tree()
            output = material_setup.get_node_tree_output(tree)
    
            # this should be diffuse
            surface_material = output.inputs[output.shader_in].links[0].from_node
    
            # create node and connect it to material input
            lookup = tree.nodes.new(type='rpr_input_node_lookup')
            tree.links.new(lookup.outputs[lookup.value_out], surface_material.inputs[surface_material.color_in])
            lookup.type = 'UV'
 

### Versioning

The version number should be updated when a new plugin is released.  This is done by editing the version field
of the bl_info structure in the src/rprblender/__init__.py file. Currently a build script will update the build
number when checkins happen to the master branch.  So it is only necessary to update the major or minor number
when required.

