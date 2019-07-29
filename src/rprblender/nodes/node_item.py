from __future__ import annotations # this is needed to use the same class type hints
import pyrpr
import math

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
                result_data.set_input('op', rpr_operation)
                result_data.set_input('color0', self.data)

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
                result_data.set_input('op', rpr_operation)
                result_data.set_input('color0', self.data)
                result_data.set_input('color1', other_data)

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
            result_data.set_input('op', rpr_key)
            result_data.set_input('color0', self.data)

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
            result_data.set_input('op', pyrpr.MATERIAL_NODE_OP_TERNARY)
            result_data.set_input('color0', self.data)
            result_data.set_input('color1', if_data)
            result_data.set_input('color2', else_data)

        return NodeItem(self.rpr_context, result_data)

    def blend(self, color0, color1):
        data0 = color0.data if isinstance(color0, NodeItem) else color0
        data1 = color1.data if isinstance(color1, NodeItem) else color1

        result_data = self.rpr_context.create_material_node(pyrpr.MATERIAL_NODE_BLEND_VALUE)
        result_data.set_input('weight', self.data)
        result_data.set_input('color0', data0)
        result_data.set_input('color1', data1)

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

        c = v * s
        h_i = h * 6.0
        x = c * (1.0 - abs(h_i % 2.0 - 1.0))
        m = v - c

        o_o = NodeItem(self.rpr_context, 0.0)

        rgb = (h_i <= 1.0).if_else(c.combine(x, 0.0),
              (h_i <= 2.0).if_else(x.combine(c, 0.0),
              (h_i <= 3.0).if_else(o_o.combine(c, x),
              (h_i <= 4.0).if_else(o_o.combine(x, c),
              (h_i <= 5.0).if_else(x.combine(0.0, c),
              (h_i <= 6.0).if_else(c.combine(0.0, x),
                                   (0.0, 0.0, 0.0) ))))))

        return rgb + m
    
    def rgb_to_hsv(self):
        ''' convert rgb back to hsv
            see cycles osl code for reference '''
        r = self.get_channel(0)
        g = self.get_channel(1)
        b = self.get_channel(2)

        mx = r.max(g.max(b))
        mn = r.min(g.min(b))
        df = mx - mn

        h = (mx == mn).if_else(0.0,
            (mx == r).if_else((g - b) / df + 6.0,
            (mx == g).if_else((b - r) / df + 2.0,
                              (r - g) / df + 4.0)))
        h = (h % 6.0) / 6.0

        s = (mx == 0.0).if_else(0.0, df / mx)
        v = mx

        return h.combine(s, v)

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
