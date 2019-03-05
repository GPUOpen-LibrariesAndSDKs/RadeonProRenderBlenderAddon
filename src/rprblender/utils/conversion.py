import math


def convert_kelvins_to_rgb_helland(color_temperature: float) -> tuple:
    """
    Convert Kelvin temperature to black body emission RGB color using approximation by Tanner Helland
    Author created approximation of data tables of Mitchell Charity
    Source: http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/
    """

    # range check
    if color_temperature < 1000:
        color_temperature = 1000
    elif color_temperature > 40000:
        color_temperature = 40000

    tmp_internal = color_temperature / 100.0
    # red
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)
        red = max(0, min(tmp_red, 255))

    # green
    if tmp_internal <= 66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661
        green = max(0, min(tmp_green, 255))
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)
        green = max(0, min(tmp_green, 255))

    # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        blue = max(0, min(tmp_blue, 255))

    return (red / 255.0, green / 255.0, blue / 255.0)


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
    if tmp_internal < 66:
        red = 255
    else:
        tmp_red = 351.97690566805693 \
                  + 0.114206453784165 * (tmp_internal - 55) \
                  - 40.25366309332127 * math.log(tmp_internal - 55)
        red = max(0.0, min(tmp_red, 255.0))

    # green
    if tmp_internal < 66:
        tmp_green = -155.25485562709179\
                    - 0.44596950469579133 * (tmp_internal - 2)\
                    + 104.49216199393888 * math.log(tmp_internal - 2)
        green = max(0.0, min(tmp_green, 255.0))
    else:
        tmp_green = 325.4494125711974 \
                    + 0.07943456536662342 * (tmp_internal - 50) \
                    - 28.0852963507957 * math.log(tmp_internal - 50)
        green = max(0.0, min(tmp_green, 255.0))

        # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 20:
        blue = 0
    else:
        tmp_blue = -254.76935184120902 \
                   + 0.8274096064007395 * (tmp_internal - 10) \
                   + 115.67994401066147 * math.log(tmp_internal - 10)
        blue = max(0.0, min(tmp_blue, 255.0))

    return (red / 255.0, green / 255.0, blue / 255.0)


# Use this conversion method for all calls
convert_kelvins_to_rgb = convert_kelvins_to_rgb_bartlett

