from __future__ import annotations # this is needed to use the same class type hints
import pyrpr, pyrprx
import math

from rprblender.utils import logging
log = logging.Log(tag='export.node')

def to_vec4(val):
        ''' val is of of type tuple, float, Node, None 
            if float or tuple make into a 4 tuple
        ''' 
        if isinstance(val, float):
            return (val, val, val, val)
        if isinstance(val, int):
            return (float(val), float(val), float(val), float(val))
        if isinstance(val, tuple) and len(val) == 3:
            return (*val, 1.0)
        return val

class NodeItem:
    ''' This class is a wrapper used for doing operations on material nodes.
        rpr_context is referenced to create new nodes 
        A Nodeitem can hold a float, vector, or Node value.  Node Items can then be simply 
        multiplied, divided, etc by using operator overloading.

        If the values are fixed, math operations will be applied, otherwise an 
        RPR arithmetic node will be created.

        NodeItems can retrieve their data with () operator, or index RGBA etc with []
        '''
    
    def __init__(self, rpr_context, data: [tuple, float, pyrpr.MaterialNode, pyrprx.Material]):
        # save the data as vec4 if num data
        self.data = to_vec4(data)
        self.rpr_context = rpr_context

    def one_is_node(self, other):
        ''' Returns if this node or another is not a fixed value ''' 
        return self.is_node() or (isinstance(other, NodeItem) and other.is_node())

    ###### MATH OPS ######
    def arithmetic_helper(self, other, rpr_type, func):
        ''' helper function for overridden math functions.  
            This simply creates an arithmetic node of rpr_type
            if one of the operands has node data, else maps the function to data '''
        if self.one_is_node(other):
            return self.create_arithmetic(other, rpr_type)
        else: 
            ''' if neither is node_type we can use "fast mode"
             takes two tuple NodeItems and applies an op returns a new NodeItem'''
            other_data = other.data if isinstance(other, NodeItem) else to_vec4(other)
            new_data = map(func, self.data, other_data)
            return NodeItem(self.rpr_context, tuple(new_data))

    def __add__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_ADD, lambda a,b: a + b)

    def __sub__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_SUB, lambda a,b: a - b)

    def __mul__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MUL, lambda a,b: a * b)

    def __truediv__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_DIV, lambda a,b: b if math.isclose(b,0.0) else a / b)

    def __mod__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MOD, lambda a,b: a % b)

    def __pow__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_POW, lambda a,b: a ** b)

    def dot(self, other):
        ''' Dot product of self with other node ''' 
        if self.one_is_node(other):
            return self.create_arithmetic(other, pyrpr.MATERIAL_NODE_OP_DOT3)
        else:
            other_data = to_vec4(other)
            return NodeItem(self.rpr_context, sum((other_data[i] * self.data[i] for i in range(4))))

    def dot4(self, other):
        ''' Dot4 product of self with other node ''' 
        if self.one_is_node(other):
            return self.create_arithmetic(other, pyrpr.MATERIAL_NODE_OP_DOT4)
        else:
            other_data = other.data if isinstance(other, NodeItem) else to_vec4(other)
            return NodeItem(self.rpr_context, sum((other_data[i] * self.data[i] for i in range(4))))

    def __neg__(self):
        return NodeItem(self.rpr_context, 0.0).create_arithmetic(self, pyrpr.MATERIAL_NODE_OP_SUB)

    def __abs__(self):
        return self.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_ABS)

    def __floor__(self):
        return self.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_FLOOR)

    # right hand methods for doing something like 1.0 - Node

    def __radd__(self, other):
        other = NodeItem(self.rpr_context, other)
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_ADD, lambda a,b: a + b)
        
    def __rsub__(self, other):
        other = NodeItem(self.rpr_context, other)
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_SUB, lambda a,b: a - b)

    def __rmul__(self, other):
        other = NodeItem(self.rpr_context, other)
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MUL, lambda a,b: a * b)


    def __rtruediv__(self, other):
        other = NodeItem(self.rpr_context, other)
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_DIV, lambda a,b: a / b)

    def __rmod__(self, other):
        other = NodeItem(self.rpr_context, other)
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MOD, lambda a,b: a % b)

    def __rpow__(self, other):
        other = NodeItem(self.rpr_context, other)
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_POW, lambda a,b: a ** b)

    ##### LOGIC OPS #####

    def __gt__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_GREATER, lambda a,b: float(a > b))

    def __ge__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_GREATER_OR_EQUAL, lambda a,b: float(a >= b))

    def __lt__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_LOWER, lambda a,b: float(a < b))

    def __le__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_LOWER_OR_EQUAL, lambda a,b: float(a <= b))

    def __eq__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_EQUAL, lambda a,b: float(a == b))
 
    def __ne__(self, other):
        return self.arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_NOT_EQUAL, lambda a,b: float(a != b))

    def __getitem__(self, key):
        if self.is_node():
            if key in {0, 'r', 'x'}:
                return self.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_SELECT_X)
            elif key in {1, 'g', 'y'}:
                return self.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_SELECT_Y)
            elif key in {2, 'b', 'z'}:
                return self.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_SELECT_Z)
            else:
                return self.create_arithmetic(None, pyrpr.MATERIAL_NODE_OP_SELECT_W)
        else:
            if key in {0, 'r', 'x'}:
                key = 0
            elif key in {1, 'g', 'y'}:
                key = 1
            elif key in {2, 'b', 'z'}:
                key = 2
            else:
                key = 3

            return NodeItem(self.rpr_context, self.data[key])

    def set_channel(self, key, value):
        ''' create new NodeItem with channel key set to a value ''' 
        if self.is_node():
            if key in {0, 'r', 'x'}:
                return NodeItem(self.rpr_context, (1.0, 0.0, 0.0, 0.0)) * value + self
            elif key in {1, 'g', 'y'}:
                return NodeItem(self.rpr_context, (0.0, 1.0, 0.0, 0.0)) * value + self
            elif key in {2, 'b', 'z'}:
                return NodeItem(self.rpr_context, (0.0, 0.0, 1.0, 0.0)) * value + self
            else:
                return NodeItem(self.rpr_context, (0.0, 0.0, 0.0, 1.0)) * value + self
        else:
            if key in {0, 'r', 'x'}:
                key = 0
            elif key in {1, 'g', 'y'}:
                key = 1
            elif key in {2, 'b', 'z'}:
                key = 2
            else:
                key = 3

            new_data = self.data
            new_data[key] = value
            return NodeItem(self.rpr_context, new_data)


    @staticmethod
    def if_else(test: NodeItem, if_value, else_value):
        ''' Construct an if - else RPR arithmetic node ''' 
        # we assume test is a NodeItem
        if not isinstance(if_value, NodeItem):
            if_value = NodeItem(test.rpr_context, if_value)

        if not isinstance(else_value, NodeItem):
            else_value = NodeItem(test.rpr_context, else_value)

        new_node_item = NodeItem(test.rpr_context, 
                                 test.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ARITHMETIC))
        new_node_item.set_input('op', pyrpr.MATERIAL_NODE_OP_TERNARY)
        new_node_item.set_input('color0', test)
        new_node_item.set_input('color1', if_value)
        new_node_item.set_input('color2', else_value)
        return new_node_item

    @staticmethod
    def blend(color0:NodeItem, color1, weight):
        ''' blend two nodeItems by weight ''' 
        node = NodeItem(color0.rpr_context,
                        color0.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BLEND_VALUE))
        node.set_input('color0', color0)
        node.set_input('color1', color1)
        node.set_input('weight', weight)

        return node


    # Other methods):
    def __call__(self):
        # return the actual node data
        return self.data

    @property
    def dtype(self):
        ''' returns if this NodeItem is static or rpr Node ''' 
        if isinstance(self.data, tuple):
            return tuple
        else:
            return 'Node'

    def is_tuple(self):
        return self.dtype == tuple

    def is_node(self):
        return self.dtype == 'Node'

    def create_arithmetic(self, other, op):
        ''' create a new NodeItem from the arithmetic operation
            This will create a new rpr node if one is a node type '''
        if type(other) != NodeItem and other is not None:
            other = NodeItem(self.rpr_context, other)

        new_node_item = NodeItem(self.rpr_context,
                                 self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ARITHMETIC))
        new_node_item.set_input('op', op)
        new_node_item.set_input('color0', self())

        if other is not None:
            new_node_item.set_input('color1', self())

        return new_node_item

    
    def to_bw(self):
        ''' Apply RGB to BW conversion for "Value" output '''
        # RGB to BW conversion constants by R-G-B channels
        R_COEF = 0.2126
        G_COEF = 0.7152
        B_COEF = 0.0722
        
        if not self.is_node():
            return NodeItem(self.rpr_context, 
                            (self.data[0] * R_COEF, self.data[1] * G_COEF, self.data[2] * B_COEF, self.data[3]))
        else:
            red = self.data[0] * (R_COEF, R_COEF, R_COEF, 0.0) 
            green = self.data[1] * (G_COEF, G_COEF, G_COEF, 0.0) 
            blue = self.data[2] * (B_COEF, B_COEF, B_COEF, 0.0) 
            alpha = self.data[3] * (0.0, 0.0, 0.0, 1.0)
            
            return red + green + blue + alpha

    @staticmethod
    def combine_node_items(a: NodeItem, b, c):
        """ Mix values to single """
        vX = a * NodeItem(a.rpr_context, (1, 0, 0))
        vY = b * NodeItem(a.rpr_context, (0, 1, 0))
        vZ = c * NodeItem(a.rpr_context, (0, 0, 1))
        
        return vX + vY + vZ

    def set_input(self, key, val):
        ''' sets the rpr node input (in data) to a value ''' 
        if self.is_node():
            if isinstance(val, NodeItem):
                self.data.set_input(key, val.data)
            else:
                self.data.set_input(key, val)
        else:
            log.warn("Trying to set input", key, "to", val, 'on', self.data)

    def hsv_to_rgb(self):
        ''' convert hsv back to rgb. 
            see cycles osl code for reference '''
        h = self[0]
        s = self[1]
        v = self[1]

        h2 = NodeItem.if_else(h == 1.0, 0.0, h * 6.0)
        i = math.floor(h2)
        f = h2 - i
        p = v * (1.0 - s)
        q = v * (1.0 - (s * f))
        t = v * (1.0 - (s * (1.0 - f)))

        rgb0 = NodeItem.if_else(i == 0.0, NodeItem.combine_node_items(v,t,p), 0.0)
        rgb1 = NodeItem.if_else(i == 1.0, NodeItem.combine_node_items(q,v,p), rgb0)
        rgb2 = NodeItem.if_else(i == 2.0, NodeItem.combine_node_items(p,v,t), rgb1)
        rgb3 = NodeItem.if_else(i == 3.0, NodeItem.combine_node_items(p,q,v), rgb2)
        rgb4 = NodeItem.if_else(i == 4.0, NodeItem.combine_node_items(t,p,v), rgb3)
        rgb5 = NodeItem.if_else(i == 5.0, NodeItem.combine_node_items(v,p, q), rgb4)

        return NodeItem.if_else(s == 0.0, v, rgb5)
    
    def rgb_to_hsv(self):
        ''' convert rgb back to hsv
            see cycles osl code for reference '''
        rgb = self.data
        r = self[0]
        g = self[1]
        b = self[2]

        cmax = NodeItem.max(r, NodeItem.max(g,b))
        cmin = NodeItem.min(r, NodeItem.min(g,b))
        cdelta = cmax - cmin

        v = cmax
        
        # have to check if cmax is a NodeItem
        s = NodeItem.if_else(cmax != 0.0, (cdelta / cmax), 0.0)
        
        c = (cmax - rgb)/ cdelta
        c_r = c[0]
        c_g = c[1]
        c_b = c[2]

        h_2 = NodeItem.if_else(g == cmax, (2.0 + (c_r - c_b)), 4.0 + (c_g - c_r))
        h_3 = NodeItem.if_else(r == cmax, (c_b - c_g), h_2)
        h_4 = h_3 / 6.0
        h_5 = NodeItem.if_else(h_4 < 0.0, h_4 + 1.0, h_4)

        h = NodeItem.if_else(s == 0.0, 0.0, h_5)

        return NodeItem.combine_node_items(h,s,v)

    def clamp(self, min_val=0.0, max_val=1.0):
        ''' clamp data to min/max ''' 
        if self.is_node():
            max_node = NodeItem.if_else(self > max_val, max_val, self)
            min_node = NodeItem.if_else(max_node < min_val, min_val, max_node)
            return min_node
        else:
            clamp_func = lambda val : min(max(val, max_val), min_val)
            return NodeItem(self.rpr_context, tuple(map(clamp_func, self.data)))

    @staticmethod
    def min(val1, val2):
        ''' min of two items ''' 
        if isinstance(val1, NodeItem) or isinstance(val2, NodeItem):
            if not isinstance(val1, NodeItem):
                val1 = NodeItem(val2.rpr_context, val1)
            elif not isinstance(val2, NodeItem):
                val2 = NodeItem(val1.rpr_context, val2)
            
            return val1.create_arithmetic(val2, pyrpr.MATERIAL_NODE_OP_MIN)
        else:
            return min(val1, val2)

    @staticmethod
    def max(val1, val2):
        ''' max of two items ''' 
        if isinstance(val1, NodeItem) or isinstance(val2, NodeItem):
            if not isinstance(val1, NodeItem):
                val1 = NodeItem(val2.rpr_context, val1)
            elif not isinstance(val2, NodeItem):
                val2 = NodeItem(val1.rpr_context, val2)
            
            return val1.create_arithmetic(val2, pyrpr.MATERIAL_NODE_OP_MAX)
        else:
            return max(val1, val2)
