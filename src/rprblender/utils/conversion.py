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
import math


def convert_kelvins_to_rgb_bartlett(color_temperature: float) -> tuple:
    """
    Convert Kelvin temperature to black body emission RGB color using approximation by Neil Bartlett
    Author used the ideas of Tanner Helland and came up with a slightly better approximation
    Source: http://www.zombieprototypes.com/?p=210
    """

    # range check
    if color_temperature < 1000:
        color_temperature = 1000
    elif color_temperature > 40000:
        color_temperature = 40000

    tmp_internal = color_temperature / 100.0
    # red
    if tmp_internal < 66.0:
        red = 255.0
    else:
        tmp_red = 351.97690566805693 \
                  + 0.114206453784165 * (tmp_internal - 55.0) \
                  - 40.25366309332127 * math.log(tmp_internal - 55.0)
        red = max(0.0, min(tmp_red, 255.0))

    # green
    if tmp_internal < 66.0:
        tmp_green = -155.25485562709179\
                    - 0.44596950469579133 * (tmp_internal - 2.0)\
                    + 104.49216199393888 * math.log(tmp_internal - 2.0)
        green = max(0.0, min(tmp_green, 255.0))
    else:
        tmp_green = 325.4494125711974 \
                    + 0.07943456536662342 * (tmp_internal - 50.0) \
                    - 28.0852963507957 * math.log(tmp_internal - 50.0)
        green = max(0.0, min(tmp_green, 255.0))

        # blue
    if tmp_internal >= 66.0:
        blue = 255.0
    elif tmp_internal <= 20.0:
        blue = 0.0
    else:
        tmp_blue = -254.76935184120902 \
                   + 0.8274096064007395 * (tmp_internal - 10.0) \
                   + 115.67994401066147 * math.log(tmp_internal - 10.0)
        blue = max(0.0, min(tmp_blue, 255.0))

    return (red / 255.0, green / 255.0, blue / 255.0)


# Use this conversion method for all calls
convert_kelvins_to_rgb = convert_kelvins_to_rgb_bartlett


def perfcounter_to_str(val):
    """ Convert perfcounter difference to time string minutes-seconds-milliseconds """
    return f"{math.floor(val / 60)}m {math.floor(val % 60)}s {math.floor((val % 1) * 1000)}ms"


def murmurh3_32(key, seed=0x0):
    """
    From Cryptomatte specification:
    https://github.com/Psyop/Cryptomatte/blob/master/specification/cryptomatte_specification.pdf
    Onle one hash is currently supported, the 32 bit variant of MurmurHash3 (Also known as MurmurHash3_x86_32)

    MurmurHash3 was written by Austin Appleby, and is placed in the public domain.
    The author hereby disclaims copyright to this source code.
    https://github.com/wc-duck/pymmh3/blob/master/pymmh3.py
    """

    key = bytearray(key.encode())

    def fmix(h):
        h ^= h >> 16
        h = (h * 0x85ebca6b) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0xc2b2ae35) & 0xFFFFFFFF
        h ^= h >> 16
        return h

    length = len(key)
    nblocks = int(length / 4)

    h1 = seed

    c1 = 0xcc9e2d51
    c2 = 0x1b873593

    # body
    for block_start in range(0, nblocks * 4, 4):
        k1 = key[block_start + 3] << 24 | \
             key[block_start + 2] << 16 | \
             key[block_start + 1] << 8 | \
             key[block_start + 0]

        k1 = (c1 * k1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        k1 = (c2 * k1) & 0xFFFFFFFF

        h1 ^= k1
        h1 = (h1 << 13 | h1 >> 19) & 0xFFFFFFFF  # inlined ROTL32
        h1 = (h1 * 5 + 0xe6546b64) & 0xFFFFFFFF

    tail_index = nblocks * 4
    k1 = 0
    tail_size = length & 3

    if tail_size >= 3:
        k1 ^= key[tail_index + 2] << 16
    if tail_size >= 2:
        k1 ^= key[tail_index + 1] << 8
    if tail_size >= 1:
        k1 ^= key[tail_index + 0]

    if tail_size > 0:
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    unsigned_val = fmix(h1 ^ length)

    # hash modified to match core results
    exponent = unsigned_val >> 23 & 255
    if exponent == 256 & exponent == 0:
        unsigned_val ^= 1 << 23
        return unsigned_val

    return unsigned_val


def get_cryptomatte_name(name: str) -> str:
    return name.replace("(", "").replace(")", "").replace(", ", "_").replace("'", "")


def get_cryptomatte_hash(name: str) -> str:
    return "%08x" % murmurh3_32(str(name))
