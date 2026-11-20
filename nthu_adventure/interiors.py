"""Three independently drawn, walkable interiors based on NTHU public references."""
from dataclasses import dataclass
import math
from random import Random

import pygame


@dataclass(frozen=True)
class Fixture:
    key: str
    point: tuple


class Room:
    def __init__(self, key, outline, entry, fixtures, labels):
        self.key = key
        self.surface = pygame.Surface((1280, 720))
        self.surface.fill((23, 29, 31))
        self.outline = outline
        self.entry = entry
        floor_image = pygame.Surface((1280, 720), pygame.SRCALPHA)
        pygame.draw.polygon(floor_image, (255, 255, 255), outline)
        self.floor = pygame.mask.from_surface(floor_image)
        self.shapes = []
        self.storage = []
        self.fixtures = (Fixture("exit", entry), *(Fixture(*item) for item in fixtures))
        self.labels = labels

    def hit(self, rect):
        if not self.surface.get_rect().contains(rect):
            return True
        samples = (rect.topleft, (rect.right - 1, rect.top), (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
        return not all(self.floor.get_at(point) for point in samples) or any(rect.colliderect(other) for other in self.shapes)

    def paint_floor(self, base, variation, *, wood=False):
        rng = Random(self.key)
        layer = pygame.Surface((1280, 720))
        width, height = ((30, 126) if wood else (35, 35))
        layer.fill(base)
        for x in range(0, 1280, width):
            offset = rng.randrange(height) if wood else 0
            for y in range(-offset, 720, height):
                light = rng.randint(-variation, variation)
                fill = tuple(channel + light for channel in base)
                pygame.draw.rect(layer, fill, (x, y, width - 1, height - 1))
                if wood:
                    for i in range(3):
                        u = x + rng.randrange(width)
                        v = y + rng.randrange(height)
                        pygame.draw.aaline(layer, tuple(c - 9 for c in fill), (u, v), (u + rng.randint(-1, 1), v + rng.randint(7, 39)))
        for _ in range(17500):
            x, y = rng.randrange(1280), rng.randrange(720)
            value = layer.get_at((x, y))
            depth = rng.randint(-10, 8)
            layer.set_at((x,y), tuple(max(0, min(255, c + depth)) for c in value[:3]))
        self.floor.to_surface(surface=self.surface, setsurface=layer, unsetcolor=None)
        self.surface.set_clip((0, 0, 1280, 617))

    def wall(self, rect, color=(116, 115, 105)):
        rect = pygame.Rect(rect)
        self.shapes.append(rect)
        pygame.draw.rect(self.surface, (58, 61, 58), rect.move(3, 6))
        pygame.draw.rect(self.surface, color, rect)
        pygame.draw.line(self.surface, tuple(c+32 for c in color), rect.topleft, rect.topright, 3)
        pygame.draw.line(self.surface, (57, 62, 59), rect.bottomleft, rect.bottomright, 3)

    def fixture(self, rect, color, kind="table", collision=True):
        x, y, w, h = rect = pygame.Rect(rect)
        if collision:
            self.shapes.append(rect.inflate(-2, -2))
            if kind in ("desk", "books", "table") and rect.width >= 48:
                container = "shelf" if kind == "books" else "drawer" if kind == "desk" else "cabinet"
                self.storage.append((rect, container))
        r, g, b = color
        highlight = (min(r + 33, 255), min(g + 33, 255), min(b + 33, 255))
        dark = (max(r - 32, 0), max(g - 32, 0), max(b - 32, 0))
        shape = pygame.draw.ellipse if kind == "round" else pygame.draw.rect
        shape(self.surface, (89, 86, 73), rect.move(5, 6))
        shape(self.surface, dark, rect)
        shape(self.surface, color, rect.inflate(-3, -4).move(0,-1))
        shape(self.surface, highlight, (x + 3, y + 2, w - 6, 3))
        if kind == "books":
            for i in range(x + 7, x + w - 5, 6):
                tint = ((183, 132, 74), (172, 172, 130), (89, 124, 123), (131, 61, 56))[i % 4]
                pygame.draw.rect(self.surface, tint, (i, y + 6, 4, h - 11))
        if kind == "sofa":
            pygame.draw.rect(self.surface, dark, (x + 3, y + 5, w - 6, h // 3), border_radius=3)
            for i in range(x + 11, x + w - 10, 15):
                pygame.draw.circle(self.surface, highlight, (i, y + 10), 1)
        if kind == "radio":
            pygame.draw.rect(self.surface, (29, 38, 36), (x+8, y+7, w-16, h-13), border_radius=3)
            pygame.draw.rect(self.surface, (233, 164, 80), (x+13, y+12, 9, 4))
            pygame.draw.line(self.surface, (51, 61, 60), (x+w-10, y+8), (x+w+3, y-11), 2)
        if kind == "desk":
            pygame.draw.rect(self.surface, (205, 192, 166), (x+6, y+5, w//4, h//2))
            pygame.draw.aaline(self.surface, dark, (x+8,y+9), (x+6+w//4,y+9))

    def door_trim(self, x, y):
        pygame.draw.rect(self.surface, (99, 79, 63), (x-14,y,28,13), border_radius=2)
        pygame.draw.line(self.surface, (196, 161, 117), (x-12,y+3),(x+11,y+3),2)
        pygame.draw.circle(self.surface, (211, 188, 131), (x+8,y+9), 1)

    def plant(self, x, y):
        self.fixture((x-10, y-7, 20, 17), (139, 100, 73), "round")
        rng = Random(x+y)
        for _ in range(17):
            px, py = x + rng.randint(-13, 10), y - rng.randint(1, 18)
            pygame.draw.ellipse(self.surface, rng.choice(((69,103,70), (115,137,81), (80,120,80))), (px, py, 9, 7))

    def finish(self):
        self.surface.set_clip(None)
        pygame.draw.lines(self.surface, (38, 43, 42), True, self.outline, 4)
        pygame.draw.circle(self.surface, (109, 129, 113), self.entry, 14, 2)
        return self


def education():
    outer = [(151, 103), (1121, 103), (1121, 606), (151, 606)]
    room = Room("education", outer, (176, 394), [
        ("class_notice", (533, 283)), ("exhibit", (705, 295)),
    ], [("room.court", (551, 483)), ("room.115", (478, 308)), ("room.113", (721, 202))])
    room.paint_floor((179, 172, 149), 10)
    room.wall((151, 103, 970, 14))
    room.wall((151, 117, 14, 246))
    room.wall((151, 428, 14, 178))
    room.wall((1106, 117, 15, 489))
    room.wall((151, 592, 970, 14))
    # Official west entrance, central court, 116–115–114 band, east-side 113 exhibit.
    for x,y,w,h in ((166,118,99,196),(279,118,108,195),(571,118,73,196),
                    (886,118,220,472),(165,535,705,56),(646,118,164,56)):
        for inset in range(4):
            pygame.draw.rect(room.surface, (118+inset*4, 119+inset*4, 107+inset*4),
                             (x+inset,y+inset,w-inset*2,h-inset*2),1)
        tint = pygame.Surface((w,h), pygame.SRCALPHA)
        tint.fill((68,78,72,92))
        room.surface.blit(tint,(x,y))
    for x in (265, 387, 557, 645):
        room.wall((x, 117, 13, 210))
    for x, w in ((165, 322), (539, 283)):
        room.wall((x, 315, w, 14))
    room.wall((810, 117, 13, 109))
    room.wall((810, 284, 13, 45))
    room.wall((646, 175, 174, 12))
    room.wall((871, 117, 14, 475))
    for y in (199, 302, 396, 494):
        room.wall((882, y, 225, 11))
    room.wall((165, 521, 672, 13))
    for x in (234, 344, 462, 578, 694, 794):
        room.door_trim(x, 521)
    for y in (244, 348, 458, 540):
        pygame.draw.rect(room.surface,(145,125,98),(873,y,9,26),border_radius=2)
        pygame.draw.line(room.surface,(217,187,134),(880,y+6),(880,y+20),1)
    for x in (274, 388, 505, 622, 738, 837):
        room.wall((x, 532, 12, 60))
    pygame.draw.rect(room.surface, (47, 73, 65), (417, 126, 103, 9), border_radius=2)
    room.fixture((446, 145, 49, 20), (139, 97, 61), "desk")
    for x in (414, 461, 512):
        for y in (189, 222, 255):
            room.fixture((x, y, 29, 13), (165, 139, 99))
            pygame.draw.rect(room.surface, (83, 103, 96), (x+8, y+16, 12, 7), border_radius=3)
    for i in range(6):
        col, row = i % 3, i // 3
        color = ((159, 154, 159), (147, 169, 164), (190, 164, 135), (157, 166, 133), (183, 155, 146), (162, 162, 134))[i]
        pygame.draw.rect(room.surface, color, (372+col*107, 366+row*50, 104, 47))
    room.fixture((243, 445, 112, 58), (144, 143, 133))
    for j in range(8):
        y = 449 + j*6
        pygame.draw.line(room.surface, (99, 104, 97), (247, y), (351, y), 2)
    pygame.draw.rect(room.surface, (140, 109, 74), (686, 181, 83, 15))
    for x in (690, 715, 741):
        pygame.draw.rect(room.surface, (217, 213, 191), (x, 184, 15, 7))
    pygame.draw.rect(room.surface, (232, 214, 165), (525, 281, 21, 22))
    room.plant(201, 498)
    room.plant(794, 475)
    for x in (388, 559, 726):
        room.fixture((x, 337, 38, 10), (135, 125, 101), collision=True)
    for y in (371, 410):
        pygame.draw.line(room.surface, (210, 204, 172), (176,y),(235,y),2)
    pygame.draw.rect(room.surface, (149, 128, 95), (681, 265, 55, 11), border_radius=2)
    pygame.draw.rect(room.surface, (201, 185, 151), (696, 267, 22, 3), border_radius=2)
    return room.finish()


def library():
    outer = [(166, 124), (1120, 124), (1120, 606), (412, 606), (360, 564), (268, 559), (166, 441)]
    room = Room("main_library", outer, (299, 536), [
        ("sample_audio", (338, 360)), ("exhibition", (656, 491)), ("books", (637, 257)),
    ], [("room.counter", (247, 315)), ("room.reserves", (640, 178)), ("room.light", (990, 485)),
        ("room.circle", (656, 382)), ("room.hub", (811, 558))])
    room.paint_floor((155, 168, 162), 9)
    room.wall((167, 124, 953, 18), (105, 128, 129))
    room.wall((167, 142, 15, 291), (109, 130, 129))
    room.wall((1104, 143, 16, 463), (109, 130, 129))
    room.wall((183, 142, 209, 127), (103, 117, 114))
    for rect in ((442,153,119,54), (757,144,95,89), (1012,144,92,108)):
        room.wall(rect, (109, 127, 126))
    for x,y in ((407,280), (505,331), (881,309), (993,322), (870,478), (409,462)):
        room.fixture((x-11, y-11, 22, 22), (206, 209, 179), "round")
    # Curved counter on the west, reserves behind the circle, southwest entry.
    room.fixture((232, 331, 88, 24), (164, 119, 72), "desk")
    room.fixture((235, 354, 27, 69), (155, 111, 69))
    room.fixture((275, 339, 29, 14), (106, 93, 74), "radio", False)
    room.fixture((584, 199, 137, 31), (126, 100, 72), "books")
    room.fixture((536, 200, 38, 73), (123, 98, 70), "books")
    for cx, cy in ((614, 285), (683, 274), (750, 282), (809, 304)):
        room.fixture((cx-24,cy,48,15), (156, 133, 91), "books")
    pygame.draw.circle(room.surface, (124, 149, 138), (655, 411), 77)
    pygame.draw.circle(room.surface, (114, 142, 133), (655, 411), 77, 3)
    for arc in [(1.1,2.75),(3.6,5.65)]:
        for i in range(5):
            angle = arc[0] + (arc[1]-arc[0]) * i/4
            x, y = round(655+61*math.cos(angle)), round(411+61*math.sin(angle))
            room.fixture((x-12,y-6,24,12), (177, 139, 87), "books")
    for x, y in ((941,380), (1031,401), (955,454), (801,530), (854,510)):
        room.fixture((x-19,y-9,38,20), (177, 143, 94), "round")
        pygame.draw.circle(room.surface,(85, 118, 111),(x-25,y+11),8)
        pygame.draw.circle(room.surface,(127, 124, 91),(x+25,y+5),8)
    for x, y in ((219, 421), (429,570), (1077,546), (918,286)):
        room.plant(x,y)
    for x, y in ((909,379),(993,392),(990,462),(847,535)):
        pygame.draw.ellipse(room.surface,(187,173,116),(x-2,y-2,4,4))
    for x,y,w,h in ((212,173,104,26),(778,166,51,12),(1040,167,40,15)):
        pygame.draw.rect(room.surface,(96,111,107),(x,y,w,h),border_radius=4)
        for dx in range(4,w-4,10):
            pygame.draw.line(room.surface,(145,151,136),(x+dx,y+4),(x+dx,y+h-4),1)
    for i in range(5):
        x, y = 305+i*13, 486+i*13
        pygame.draw.line(room.surface, (91, 117, 116), (x-12,y+10), (x+8,y-10), 3)
    return room.finish()


def xin():
    outer = [(247, 275), (559, 275), (559, 147), (1106, 147), (1106, 595), (247, 595)]
    room = Room("xin_hall", outer, (276, 531), [
        ("common_radio", (965, 240)), ("lounge", (758, 265)), ("board", (396, 445)),
    ], [("room.hallway", (390, 533)), ("room.lounge", (838, 484))])
    room.paint_floor((162, 137, 107), 12, wood=True)
    pygame.draw.rect(room.surface, (154, 151, 131), (249, 276, 308, 317))
    for x in range(250, 557, 31):
        pygame.draw.line(room.surface, (170,166,145), (x,276), (x,590))
    for y in range(277, 595, 35):
        pygame.draw.line(room.surface, (170,166,145), (249,y), (557,y))
    room.wall((247,275,312,15))
    room.wall((247,289,15,213))
    room.wall((247,562,15,33))
    room.wall((560,148,15,260))
    room.wall((560,493,15,102))
    room.wall((565,147,542,17))
    room.wall((1090,160,16,435))
    room.wall((247,582,859,13))
    pygame.draw.rect(room.surface, (66, 91, 94), (598, 166, 324, 26))
    for x in range(600,922,35):
        pygame.draw.line(room.surface, (134, 164, 153), (x,168), (x+16,190), 1)
        pygame.draw.line(room.surface, (159, 180, 164), (x,190), (x+16,168), 1)
    room.fixture((601,184,309,19), (147, 112, 76))
    for x,c in ((659,(194,140,82)),(725,(134,124,163)),(812,(169,112,72))):
        room.fixture((x,214,22,18), c, "round")
    for x,y in ((665,337), (790,290), (957,429)):
        color = (217, 216, 193) if x<900 else (153,113,81)
        room.fixture((x-34,y-18,68,37), color, "round")
        for dx,dy,tint in ((-44,18,(79,122,99)),(31,13,(171,91,73)),(-4,27,(118,145,153))):
            room.fixture((x+dx,y+dy,19,21), tint, "round")
    room.fixture((906,350,154,39), (57, 66, 66), "sofa")
    room.fixture((931,508,125,33), (63, 69, 67), "sofa")
    room.fixture((929,193,107,28), (111, 89, 67), "desk")
    room.fixture((983,197,34,20), (98,84,62), "radio", False)
    room.fixture((386,411,81,22), (130,98,65), "desk")
    room.plant(1065, 545)
    room.plant(606, 537)
    pygame.draw.rect(room.surface,(111,95,73),(296,502,54,38),border_radius=3)
    pygame.draw.rect(room.surface,(141,122,88),(299,506,48,30),2,border_radius=3)
    for i in range(6):
        pygame.draw.line(room.surface,(121,105,77),(301,509+i*4),(345,509+i*4),1)
    for x in (656, 725, 804):
        pygame.draw.aaline(room.surface,(198,169,122),(x,199),(x+33,243))
    for x,y in ((625,327),(787,286),(943,425)):
        pygame.draw.circle(room.surface,(104,127,97),(x,y),3)
        pygame.draw.line(room.surface,(140,148,110),(x-4,y-1),(x+5,y+1),2)
    room.plant(1063, 246)
    for i in range(3):
        pygame.draw.circle(room.surface, (67, 65, 56), (944+i*24, 178), 6)
        pygame.draw.circle(room.surface, (183, 156, 103), (944+i*24, 178), 2)
    return room.finish()


def create_rooms():
    from .public_interiors import public_interiors

    originals = education(), library(), xin()
    for room, point in zip(originals, ((632,487),(557,489),(818,455)), strict=True):
        room.event_point = point
    rooms = {room.key: room for room in (*originals, *public_interiors())}
    anchors = {
        "education": (745, 473), "main_library": (763, 485), "xin_hall": (769, 397),
        "general_2": (687, 466), "general_3": (726, 483), "general_4": (842, 468),
        "engineering_1": (701, 480), "physics": (686, 482), "chemistry": (736, 509),
        "gym": (624, 319), "dining_hall": (579, 283), "ren_hall": (534, 348),
        "shi_hall": (757, 302), "li_hall": (737, 496), "yi_hall": (719, 446),
        "admin_hall": (672, 508), "engineering_2": (634, 528), "computer_science": (733, 438),
        "student_center": (607, 473), "humanities_building": (739, 487),
    }
    for key, room in rooms.items():
        room.story_point = anchors[key]
    return rooms
