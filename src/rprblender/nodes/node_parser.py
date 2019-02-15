import pyrpr
import pyrprx
from . import MaterialError

from rprblender.utils import logging
log = logging.Log(tag='material', level='debug')


# Helper functions

def get_node_socket(to_node, name=None, index=None):
    ''' get the node connected to input socket name | index on in_node '''
    if name:
        socket = to_node.inputs.get(name, None)
        if socket is None:
            return None
    elif index:
        if index < len(to_node.inputs):
            socket = to_node.inputs[index]
        else:
            return None
    else:
        return None

    log("get_node_socket({}, {}, {}): {}; linked {}".
        format(to_node, name, index, socket,
               "{}; links number {}".format(socket.is_linked, len(socket.links)) if socket.is_linked else "False"))

    if socket.is_linked:
        if socket.links[0].is_valid:
            return socket.links[0].from_socket

        log.error("Invalid link found: <{}>.{} to <{}>.{}".
                  format(socket.links[0].from_node.name, socket.links[0].from_socket.name,
                         socket.links[0].to_node.name, socket.links[0].to_socket.name))
    return None


def get_node_value(material_exporter, node, socket_key):
    ''' Try to get value from 
        1.  Input link
        2.  Input default val
        3.  Node param (if no socket name) '''
    val = None
    # here we have to deal with string or int socket keys
    socket = node.inputs[socket_key] if isinstance(socket_key, int) or socket_key in node.inputs else None

    if socket and socket.is_linked:
        val = get_socket_link(material_exporter, node, socket_key)
        if val == None:
            val = get_socket_default(node, socket_key)
    # need this for if the incoming node is None (not supported)
    elif socket:
        val = get_socket_default(node, socket_key)
    else:
        val = getattr(node, socket_key, None)
        
    return val


def get_socket_link(material_exporter, node, socket_key):
    ''' Given a node and input socket, call material.parse_node on the connected node '''
    socket = node.inputs[socket_key]

    if socket.is_linked:
        link = socket.links[0]
        if link.is_valid:
            return material_exporter.parse_node(link.from_node, link.from_socket)

        log.error(
            "Invalid link found: <{}>.{} to <{}>.{}".format(
                link.from_node.name, link.from_socket.name,
                link.to_node.name, link.to_socket.name
            ),
        )

    return None

def parse_val(val):
    ''' turn a blender node val or default value for input into 
        something that works well with rpr '''
    if isinstance(val, (int, float, bool)):
        fval = float(val)
        return (fval, fval, fval, fval)

    if len(val) in (3, 4):
        return tuple(val)

    raise MaterialError("Unknown value type to pass to rpr", val)

    
def get_socket_default(node, socket_key):
    ''' get the default_value from a socket '''
    socket = node.inputs[socket_key]
    val = socket.default_value
    return parse_val(val)


def get_rpr_val(val_str: str):
    ''' turns a string such as RPR_MATERIAL_NODE_DIFFUSE into a key 
        such as pyrpr.MATERIAL_NODE_DIFFUSE '''
    rpr_val = None
    if val_str.startswith("RPR_"):
        rpr_val = getattr(pyrpr, val_str[4:], None)
    elif val_str.startswith("RPRX_"):
        rpr_val = getattr(pyrprx, val_str[5:], None)

    # rpr_val could be 0
    if rpr_val is None:
        raise MaterialError("Unknown RPR value '{}'!".format(val_str))
    else:
        return rpr_val


###########################

class NodeParser:
    ''' This is a class that parses a blender node.
        It creates RPR nodes, and takes the inputs to the blender nodes,
        hooks up all the nodes, then returns a node for the output 

        Subclasses can override gather_inputs, create_nodes, sync, as needed.
        Or simply use the basic functionality and specify the inputs and nodes of the 
        subclass and let it run.
        '''

    # A list of inputs.  These can be Input sockets, or parameters on the blender node
    inputs = []

    # RPR nodes to create.  These are nodes by name, and inputs to them.
    # outputs map by name to node names
    nodes = {}

    def __init__(self, material_exporter, blender_node):
        self.material_exporter = material_exporter
        self.blender_node = blender_node

    def get_blender_node_inputs(self):
        ''' Gather the inputs from the list of needed ones off the blender node'''
        input_vals = {}
        for input_name in self.inputs:
            # special case to deal with int input keys
            input_key = str(input_name) if isinstance(input_name, int) else input_name
            input_vals[input_key] = get_node_value(self.material_exporter, self.blender_node, input_name)
        return input_vals

    def create_rpr_nodes(self, nodes_to_create):
        ''' create a set of rpr nodes based on list of (name, type_string) 
            where type_str is RPR_MATERIAL_NODE_DIFFUSE for instance '''
        return {node_name: self.material_exporter.create_rpr_node(node_type, self.get_subnode_key(node_name)) 
                for node_name, node_type in nodes_to_create}

    def get_rpr_param_values(self, node_params, rpr_nodes, blender_inputs):
        ''' Get the input params  for a node based on the node_info dictionary.  
            This should be in the form of { 'param_name': param_val}
            Valid "values" are int/float/tuples, nodes, and strings
            of the form of 'input.input_name' or nodes.node_name '''
        parsed_params = {}

        for param_name, value_source in node_params.items():
            # is it the value source name?
            if isinstance(value_source, str):
                # blender node inputs
                if value_source.startswith('inputs.'):
                    target_name = value_source.split('inputs.')[1]
                    if target_name in blender_inputs:
                        value = blender_inputs[target_name]

                        # special case for normal if unlinked. should this be more robust and check if type is normal?
                        if target_name in {'Normal', 'Clearcoat Normal'} and isinstance(value, tuple):
                            continue
                    else:
                        log.warn("Could not find '{}' on '{}'.'{}'!".format(value_source, self.material_exporter.material.name, self.blender_node.name))
                        continue
                # internal node links
                elif value_source.startswith('nodes.'):
                    target_name = value_source.split('nodes.')[1]
                    if target_name in rpr_nodes:
                        value = rpr_nodes[target_name]
                    else:
                        log.warn("Could not find '{}' on '{}'.'{}'!".format(value_source, self.material_exporter.material.name, self.blender_node.name))
                        continue
                elif value_source.startswith('RPR'):
                    # this is an rpr value
                    value = get_rpr_val(value_source)
                else:
                    log.warn("Could not find '{}' on '{}'.'{}'!".format(value_source, self.material_exporter.material.name, self.blender_node.name))
                    continue
            else:  # Constant value
                if isinstance(value_source, (tuple, list)):
                    value = tuple(value_source)
                else:  # int, float
                    value = value_source


            parsed_params[param_name] = value

        return parsed_params


    def set_rpr_node_inputs(self, rpr_node, inputs_dict):
        ''' set the inputs to an rpr node for each input_name, value in the dict '''
        for input_name, value in inputs_dict.items():
            param_name = get_rpr_val(input_name) if input_name.startswith('RPR') else input_name
            val = get_rpr_val(value) if isinstance(value, str) and input_name.startswith('RPR') else value
            if val:
                try:
                    rpr_node.set_input(param_name, val)
                except TypeError as e:
                    raise MaterialError("Socket '{}' value assign error on node type {} '{}'.'{}'".
                                        format(param_name, type(self.blender_node).__name__, 
                                               self.material_exporter.material.name, self.blender_node.name), val)

    def set_all_node_inputs(self, rpr_nodes, blender_inputs):
        ''' loop over all node info, get the param inputs and set them on the rpr_node '''
        for node_name, node_params_info in self.nodes.items():
            node_params = self.get_rpr_param_values(node_params_info['params'], rpr_nodes, blender_inputs)
            self.set_rpr_node_inputs(rpr_nodes[node_name], node_params)


    def export(self, socket):
        ''' export all the sub nodes based on the rules in self.nodes, inputs.  
            can be overridden for complex classes '''
        
        # get the needed inputs from the blender node
        blender_inputs = self.get_blender_node_inputs()

        # create rpr nodes based on the layout
        rpr_nodes = self.create_rpr_nodes([(node_name, node_info['type']) for node_name, node_info in self.nodes.items()])
        
        # set rpr inputs from param layour and inputs
        self.set_all_node_inputs(rpr_nodes, blender_inputs)

        if socket.name not in rpr_nodes:
            # some output sockets we might not translate
            log.warn("Output '{}'' not translated for node type '{}' on '{}'.'{}'!".format(socket.name, type(self.blender_node).__name__, self.material_exporter.material.name, self.blender_node.name))
            return None
        else:
            return rpr_nodes[socket.name]


    def get_subnode_key(self, subnode_name):
        ''' get the key for a new node with subnode_name '''
        return self.material_exporter.get_node_key(self.blender_node, subnode_name)




