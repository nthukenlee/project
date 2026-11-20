"""Original illustrated character poses, rendered from layered vector shapes."""
from math import pi, sin

import pygame

INK = (39, 43, 42)
HAIR = ((56, 44, 41), (33, 38, 44), (116, 71, 49), (93, 51, 63), (167, 131, 76))
SKIN = ((238, 199, 167), (216, 173, 135), (171, 119, 85), (119, 76, 54))
COATS = ((67, 113, 111), (114, 89, 130), (149, 88, 64), (71, 101, 144), (154, 120, 62), (79, 119, 78))


def shade(color, delta):
    return tuple(max(0, min(255, value + delta)) for value in color)


def curve(points):
    """Interpolate closed silhouettes while retaining their original proportions."""
    output = []
    count = len(points)
    for index, start in enumerate(points):
        end = points[(index + 1) % count]
        previous = points[index - 1]
        after = points[(index + 2) % count]
        for i in range(5):
            t = i / 5
            pos = tuple(round(.5 * ((2*b) + (-a+c)*t + (2*a-5*b+4*c-d)*t*t
                                    + (-a+3*b-3*c+d)*t*t*t))
                        for a, b, c, d in zip(previous, start, end, after))
            output.append(pos)
    return output


def figure(facing, frame, appearance):
    canvas = pygame.Surface((150, 226), pygame.SRCALPHA)
    woman = bool(appearance.get("gender", 0))
    skin = SKIN[appearance.get("skin", 1)]
    hair = HAIR[appearance.get("hair_color", 0)]
    coat = COATS[appearance.get("shirt", 0)]
    style = appearance.get("hair_style", 0)
    side = facing in ("left", "right")
    back = facing == "up"
    hip = 20 if woman else 18
    shoulder = (21 if woman else 28) if not side else (15 if woman else 18)
    step = 0 if frame == 0 else round(10 * sin((frame-1) * pi / 4))
    lean = 1 if side and frame else 0

    def point(x, y):
        return 75 + x + lean, y

    def polygon(color, points, *, smooth=False, edge=True):
        pts = curve(points) if smooth else points
        scaled = [point(x, y) for x, y in pts]
        pygame.draw.polygon(canvas, color, scaled)
        if edge:
            pygame.draw.lines(canvas, INK, True, scaled, 2)

    def line(color, points, width=2):
        pygame.draw.lines(canvas, color, False, [point(x,y) for x, y in points], width)

    def ellipse(color, x, y, w, h, edge=False):
        pygame.draw.ellipse(canvas, color, (*point(x,y), w, h))
        if edge:
            pygame.draw.ellipse(canvas, INK, (*point(x,y), w, h), 2)

    long_hair = (woman and style in (0, 2, 3)) or style == 3
    if long_hair:
        length = 92 if style == 0 else 107 if style == 2 else 83
        polygon(shade(hair,-14), ((-19,31),(-20,65),(-24,length-6),(-9,length),
                                 (14,length-5),(22,length-12),(19,36)), smooth=True)

    for i in (-1, 1):
        reach = step * i if side else round(step * i * .45)
        x = i * (8 if side else 12)
        foot_y = 213 - (max(0, i * step) // 2 if not side else abs(step) // 4)
        trousers = (55, 61, 65) if woman else (51, 60, 67)
        polygon(shade(trousers, 5*i), ((x-8,137),(x+8,137),(x+6+reach,foot_y-4),
                                     (x-6+reach,foot_y-5)), smooth=False)
        line(shade(trousers,19), ((x-2,152),(x-1+reach//2,178),(x-2+reach,foot_y-8)))
        polygon((78, 79, 73), ((x-8+reach,foot_y-6),(x+3+reach,foot_y-6),
                              (x+10+reach,foot_y),(x+11+reach,foot_y+4),(x-9+reach,foot_y+4)), smooth=True)
        line((182,173,148), ((x-7+reach,foot_y+2),(x+9+reach,foot_y+2)))

    for i in (-1,1):
        upper = i * shoulder
        swing = i * step
        hand_x = upper + i * (3 if not side else 1) + (swing if side else 0)
        hand_y = 138 - abs(swing)//3
        polygon(shade(coat,-10 if i > 0 else 5),
                ((upper-i*7,75),(upper+i*4,77),(hand_x+i*5,117),
                 (hand_x+i*4,hand_y-5),(hand_x-i*5,hand_y-6),(upper-i*7,97)), smooth=True)
        ellipse(shade(skin,-7), hand_x-4, hand_y-7, 8, 13, True)
        line(shade(coat,27), ((upper,87),(hand_x,hand_y-13)))

    polygon(shade(skin,-12), ((-9,55),(9,55),(9,74),(0,83),(-9,74)), smooth=True)
    waist = 13 if woman else 20
    if side:
        waist -= 4
        hip -= 4
    polygon(coat, ((-shoulder+2,76),(-10,69),(0,78),(10,69),(shoulder-2,76),
                   (waist,112),(hip,134),(0,141 if woman else 137),(-hip,134),(-waist,111)),
            smooth=True)
    polygon(shade(coat,22), ((-shoulder+4,79),(-8,74),(-4,109),(-hip+1,132),(-waist,110)),
            edge=False)
    if back:
        polygon(shade(coat,-34), ((-14,80),(13,78),(17,115),(11,133),(-12,133),(-17,113)),
                smooth=True)
        line(shade(coat,18), ((-13,113),(0,116),(13,112)))
        line((168,150,110), ((-7,94),(7,94)))
    elif woman:
        polygon((224,213,185), ((-9,73),(0,82),(8,73),(7,108),(-8,108)), smooth=True, edge=False)
        line((144,103,72), ((-shoulder+4,80),(-1,102),(10,127)), 4)
        polygon((125,88,65), ((9,120),(19,121),(20,136),(8,138),(3,128)), smooth=True)
        line((193,146,98), ((7,124),(16,125),(17,129)), 2)
        line(shade(coat,30), ((-15,114),(0,118),(13,114)))
    else:
        polygon((216,211,190), ((-8,74),(0,82),(9,74),(6,129),(-7,131)), smooth=True, edge=False)
        line(shade(coat,-45), ((1,84),(2,106),(1,129)))
        line(shade(coat,26), ((-shoulder+6,91),(-12,100),(-12,122)))
        polygon(shade(coat,-25), ((9,93),(21,91),(19,104),(10,105)), edge=False)
        line((170,140,91), ((11,96),(18,95)))
    line(shade(coat,-24), ((-hip+3,132),(0,138 if woman else 134),(hip-2,132)))
    line(shade(coat,33), ((-shoulder+8,77),(-10,72)))

    head_w = 16 if woman else 19
    if side:
        polygon(skin, ((-13,28),(-14,47),(-8,62),(5,66),(14,58),(16,47),(21,43),
                       (17,40),(14,30),(6,21),(-8,22)), smooth=True)
        line(shade(skin,-36), ((5,58),(12,55),(15,49)))
        ellipse(shade(skin,-13), -13, 38, 8, 11, True)
        if not back:
            line((53,47,46), ((8,39),(14,39)), 2)
            ellipse((43,46,43), 12, 42, 4, 5)
            line(shade(skin,-53), ((13,53),(17,52)))
    else:
        polygon(skin, ((-head_w,31),(-head_w,46),(-head_w+4,56),(-8,64),(0,67),
                       (9,64),(head_w-4,56),(head_w,45),(head_w,31),(10,23),(-10,23)), smooth=True)
        ellipse(shade(skin,-8), -head_w-4, 42, 8, 12, True)
        ellipse(shade(skin,-8), head_w-4, 42, 8, 12, True)
        if not back:
            polygon(shade(skin,11), ((-9,34),(10,35),(11,47),(6,55),(0,57),(-8,54),(-11,45)),
                    smooth=True, edge=False)
            for i in (-1,1):
                eyebrow = (hair[0]//2+18, hair[1]//2+18, hair[2]//2+18)
                line(eyebrow, ((i*6,40),(i*12,39 if woman else 40)), 2)
                ellipse((240,232,217), i*9-3, 43, 6, 4)
                ellipse((47,51,46), i*9-1, 43, 3, 4)
            line(shade(skin,-28), ((1,46),(3,51),(0,52)))
            line((132,75,66), ((-4,58),(0,59),(5,57 if woman else 58)))
            if woman:
                ellipse(shade(skin,-9), -14, 50, 5, 2)
                ellipse(shade(skin,-9), 10, 50, 5, 2)

    fringe = (
        ((-20,35),(-15,22),(-3,18),(14,22),(19,32),(16,38),(7,33),(2,41),(-5,34),(-14,44)),
        ((-21,33),(-16,20),(0,17),(17,23),(21,36),(16,45),(8,34),(-3,29),(-9,35),(-16,43)),
        ((-22,33),(-19,22),(-11,18),(-2,15),(6,19),(14,19),(21,25),(21,37),(15,42),
          (10,34),(3,38),(-5,33),(-12,40),(-18,43)),
        ((-20,33),(-12,20),(1,17),(16,24),(19,37),(13,43),(4,31),(-4,29),(-13,40),(-18,47)),
    )[style]
    if back:
        fringe = tuple((x, y + (14 if y >= 35 else 0)) for x,y in fringe)
    if side:
        fringe = tuple((round(x*.86)-3, y + (6 if x < -11 and y > 32 else 0)) for x,y in fringe)
    polygon(hair, fringe, smooth=True)
    highlight = shade(hair,31)
    line(highlight, ((-13,26),(-7,22),(1,21),(9,24)))
    line(shade(hair,18), ((-14,30),(-8,26),(-1,25)))
    line(shade(hair,-12), ((5,26),(11,29),(14,34)))
    if style == 3 and long_hair:
        ellipse((131,106,72), -20 if side else 10, 49, 5, 4)
    if facing == "left":
        canvas = pygame.transform.flip(canvas, True, False)
    return canvas
