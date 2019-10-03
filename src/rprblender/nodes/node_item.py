from __future__ import annotations # this is needed to use the same class type hints
import math

import pyrpr
from rprblender.engine import context_hybrid

from rprblender.utils import logging
log = logging.Log(tag='export.node')


class NodeItem:
    ''' This class is a wrapper used for doing operations on material nodes.
        rpr_context is referenced to create new nodes 
        A Nodeitem can hold a float, vector, or Node value.  Node Items can then be simply 
        multiplied, divided, etc by using operator overloading.

        If the values are fixed, math operations will be applied, otherwise an 
        RPR arithmetic node will be created.

        NodeItems can retrieve their data with () operator, or index RGBA etc with []
        '''
    
    def __init__(self, rpr_context, data: [tuple, float, pyrpr.MaterialNode]):
        # save the data as vec4 if num data
        self.data = data
        self.rpr_context = rpr_context

    def set_input(self, name, value):
        if value is not None:
            self.data.set_input(name, value.data if isinstance(value, NodeItem) else value)

    ###### MATH OPS ######
    def _arithmetic_helper(self, other, rpr_operation, func):
        ''' helper function for overridden math functions.
            This simply creates an arithmetic node of rpr_type
            if one of the operands has node data, else maps the function to data '''

        if other is None:
            if isinstance(self.data, float):
                result_data = func(self.data)
            elif isinstance(self.data, tuple):
                result_data = tuple(map(func, self.data))
            else:
                result_data = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ARITHMETIC)
                result_data.set_input(pyrpr.MATERIAL_INPUT_OP, rpr_operation)
                result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR0, self.data)

        else:
            other_data = other.data if isinstance(other, NodeItem) else other
            if isinstance(self.data, (float, tuple)) and isinstance(other_data, (float, tuple)):
                if isinstance(self.data, float) and isinstance(other_data, float):
                    result_data = func(self.data, other_data)
                else:
                    data = self.data

                    # converting data or other_data to have equal length
                    if isinstance(data, float):
                        data = (data,) * len(other_data)
                    elif isinstance(other_data, float):
                        other_data = (other_data,) * len(data)
                    elif len(data) < len(other_data):
                        data = (*data, 1.0)
                    elif len(other_data) < len(data):
                        other_data = (*other_data, 1.0)

                    result_data = tuple(map(func, data, other_data))

            else:
                result_data = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ARITHMETIC)
                result_data.set_input(pyrpr.MATERIAL_INPUT_OP, rpr_operation)
                result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR0, self.data)
                result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR1, other_data)

        return NodeItem(self.rpr_context, result_data)

    def __add__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_ADD, lambda a, b: a + b)

    def __sub__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_SUB, lambda a, b: a - b)

    def __mul__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MUL, lambda a, b: a * b)

    def __truediv__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_DIV,
                                       lambda a, b: a / b if not math.isclose(b, 0.0) else 0.0)

    def __mod__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MOD, lambda a, b: a % b)

    def __pow__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_POW, lambda a, b: a ** b)

    def __neg__(self):
        return 0.0 - self

    def __abs__(self):
        return self._arithmetic_helper(None, pyrpr.MATERIAL_NODE_OP_ABS, lambda a: abs(a))

    def floor(self):
        return self._arithmetic_helper(None, pyrpr.MATERIAL_NODE_OP_FLOOR,
                                       lambda a: float(math.floor(a)))

    def ceil(self):
        f = self.floor()
        return (self == f).if_else(self, f + 1.0)

    def fract(self):
        return self - self.floor()

    # right hand methods for doing something like 1.0 - Node
    def __radd__(self, other):
        return self + other
        
    def __rsub__(self, other):
        if not isinstance(other, NodeItem):
            other = NodeItem(self.rpr_context, other)
        return other - self

    def __rmul__(self, other):
        return self * other

    def __rtruediv__(self, other):
        if not isinstance(other, NodeItem):
            other = NodeItem(self.rpr_context, other)
        return other / self

    def __rmod__(self, other):
        if not isinstance(other, NodeItem):
            other = NodeItem(self.rpr_context, other)
        return other % self

    def __rpow__(self, other):
        if not isinstance(other, NodeItem):
            other = NodeItem(self.rpr_context, other)
        return other ** self

    ##### LOGIC OPS #####

    def __gt__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_GREATER,
                                       lambda a, b: float(a > b))

    def __ge__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_GREATER_OR_EQUAL,
                                       lambda a, b: float(a >= b))

    def __lt__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_LOWER,
                                       lambda a, b: float(a < b))

    def __le__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_LOWER_OR_EQUAL,
                                       lambda a, b: float(a <= b))

    def __eq__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_EQUAL,
                                       lambda a, b: float(a == b))
 
    def __ne__(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_NOT_EQUAL,
                                       lambda a,b: float(a != b))

    def get_channel(self, key):
        if isinstance(self.data, float):
            result_data = self.data
        elif isinstance(self.data, tuple):
            result_data = self.data[key] if key < len(self.data) else 1.0
        else:
            rpr_key = {
                0: pyrpr.MATERIAL_NODE_OP_SELECT_X,
                1: pyrpr.MATERIAL_NODE_OP_SELECT_Y,
                2: pyrpr.MATERIAL_NODE_OP_SELECT_Z,
                3: pyrpr.MATERIAL_NODE_OP_SELECT_W,
            }[key]

            result_data = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ARITHMETIC)
            result_data.set_input(pyrpr.MATERIAL_INPUT_OP, rpr_key)
            result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR0, self.data)

        return NodeItem(self.rpr_context, result_data)

    def dot3(self, other):
        dot = self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_DOT3, lambda a, b: a * b)
        if isinstance(dot.data, float):
            dot.data *= 3
        elif isinstance(dot.data, tuple):
            dot.data = sum(dot.data[:3])

        return dot

    def dot4(self, other):
        dot = self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_DOT4, lambda a, b: a * b)
        if isinstance(dot.data, float):
            dot.data *= 4
        elif isinstance(dot.data, tuple):
            dot.data = sum(dot.data)

        return dot

    def if_else(self, if_value, else_value):
        ''' Construct an if - else RPR arithmetic node ''' 
        # we assume test is a NodeItem
        if_data = if_value.data if isinstance(if_value, NodeItem) else if_value
        else_data = else_value.data if isinstance(else_value, NodeItem) else else_value

        if isinstance(self.data, float):
            result_data = if_data if bool(self.data) else else_data
        else:
            result_data = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_ARITHMETIC)
            result_data.set_input(pyrpr.MATERIAL_INPUT_OP, pyrpr.MATERIAL_NODE_OP_TERNARY)
            result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR0, self.data)
            result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR1, if_data)
            result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR2, else_data)

        return NodeItem(self.rpr_context, result_data)

    def blend(self, color0, color1):
        if isinstance(self.rpr_context, context_hybrid.RPRContext):
            return self * color1 + (1.0 - self) * color0

        data0 = color0.data if isinstance(color0, NodeItem) else color0
        data1 = color1.data if isinstance(color1, NodeItem) else color1

        result_data = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BLEND_VALUE)
        result_data.set_input(pyrpr.MATERIAL_INPUT_WEIGHT, self.data)
        result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR0, data0)
        result_data.set_input(pyrpr.MATERIAL_INPUT_COLOR1, data1)

        return NodeItem(self.rpr_context, result_data)

    def min(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MIN, lambda a, b: min(a, b))

    def max(self, other):
        return self._arithmetic_helper(other, pyrpr.MATERIAL_NODE_OP_MAX, lambda a, b: max(a, b))

    def clamp(self, min_val=0.0, max_val=1.0):
        ''' clamp data to min/max '''
        return self.min(max_val).max(min_val)

    def to_bw(self):
        ''' Apply RGB to BW conversion for "Value" output '''
        # RGB to BW conversion constants by R-G-B channels
        R_COEF = 0.2126
        G_COEF = 0.7152
        B_COEF = 0.0722

        r = self.get_channel(0) * (R_COEF, R_COEF, R_COEF, 0.0)
        g = self.get_channel(1) * (G_COEF, G_COEF, G_COEF, 0.0)
        b = self.get_channel(2) * (B_COEF, B_COEF, B_COEF, 0.0)
        a = self.get_channel(3) * (0.0, 0.0, 0.0, 1.0)

        return r + g + b + a

    def combine(self, b, c):
        """ Mix values to single """
        x = NodeItem(self.rpr_context, (1, 0, 0)) * self
        y = NodeItem(self.rpr_context, (0, 1, 0)) * b
        z = NodeItem(self.rpr_context, (0, 0, 1)) * c
        
        return x + y + z

    def combine4(self, b, c, d):
        """ Mix values to single """
        x = NodeItem(self.rpr_context, (1, 0, 0, 0)) * self
        y = NodeItem(self.rpr_context, (0, 1, 0, 0)) * b
        z = NodeItem(self.rpr_context, (0, 0, 1, 0)) * c
        w = NodeItem(self.rpr_context, (0, 0, 0, 1)) * d
        
        return x + y + z + w

    def hsv_to_rgb(self):
        ''' convert hsv back to rgb. 
            see cycles osl code for reference '''
        h = self.get_channel(0)
        s = self.get_channel(1)
        v = self.get_channel(2)

        K_x = 1.0
        K_y = 2.0/3.0
        K_z = 1.0/3.0
        K_w = 3.0
        K = NodeItem(self.rpr_context, (K_x, K_y, K_z))

        p = abs((h + K).fract() * 6.0 - K_w)
        return s.blend(K_x, (p-K_x).clamp()) * v
    
    def rgb_to_hsv(self):
        ''' convert rgb back to hsv
            see cycles osl code for reference '''
        r = self.get_channel(0)
        g = self.get_channel(1)
        b = self.get_channel(2)

        K_x = 0.0
        K_y = -1.0/3.0
        K_z = 2.0/3.0
        K_w = -1.0

        p = (g < b).if_else(b.combine4(g, K_w, K_z), g.combine4(b, K_x, K_y))
        p_x = p.get_channel(0)
        p_y = p.get_channel(1)
        p_z = p.get_channel(2)
        p_w = p.get_channel(3)
        q = (r < p_x).if_else(p_x.combine4(p_y, p_w, r), r.combine4(p_y, p_z, p_x))
        q_x = q.get_channel(0)
        q_y = q.get_channel(1)
        q_z = q.get_channel(2)
        q_w = q.get_channel(3)

        d = q_x - min(q_w, q_y)
        e = 1.0e-10

        h = abs(q_z + ((q_w - q_y) / (6.0 * d + e)))
        s = d / (q_x + e)
        return h.combine(s, q_x)

    def normalize(self):
        norm = self._arithmetic_helper(None, pyrpr.MATERIAL_NODE_OP_NORMALIZE3, lambda a: a)
        if isinstance(norm.data, float):
            # converting to vector
            norm.data = (norm.data, norm.data, norm.data)

        if isinstance(norm.data, tuple):
            length = math.sqrt(sum(norm.data[i]*norm.data[i] for i in range(3)))
            norm.data = (0.0, 0.0, 1.0) if math.isclose(length, 0.0) else \
                        (norm.data[0]/length, norm.data[1]/length, norm.data[2]/length)

        return norm

    def average_xyz(self):
        avg = self._arithmetic_helper(None, pyrpr.MATERIAL_NODE_OP_AVERAGE_XYZ, lambda a: a)
        if isinstance(avg.data, tuple):
            avg.data = sum(avg.data[:3]) / 3

        return avg
