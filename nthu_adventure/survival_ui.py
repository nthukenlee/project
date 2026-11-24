"""Shared controls and artwork for the survival interface."""
from dataclasses import dataclass
import math

import pygame

from .constants import ROOT, TILE, WINDOW_SIZE
from .content import BUILDINGS, ISLANDS, LANDSCAPES, ROADS, SPORTS_FIELDS, WALKWAYS, WATERS

INK = (13, 21, 21)
PANEL = (21, 32, 31)
PAPER = (243, 238, 224)
MUTED = (178, 188, 179)
GOLD = (244, 196, 128)
RED = (238, 155, 131)
BLUE = (139, 189, 198)
LINE = (64, 80, 74)
TRACK = (57, 71, 65)


@dataclass(frozen=True)
class MapColors:
    paper: tuple
    ink: tuple
    grid: tuple
    contour: tuple
    grass: tuple
    water: tuple
    shore: tuple
    road: tuple
    curb: tuple
    building: tuple
    outline: tuple
    alert: tuple = (137, 46, 37)
    route: tuple = (34, 91, 81)


DIRECTORY = MapColors(
    (233, 233, 214), (49, 73, 66), (213, 218, 194), (165, 179, 152),
    (192, 208, 166), (140, 180, 172), (84, 131, 120), (252, 244, 217),
    (166, 173, 151), (147, 135, 165), (83, 75, 99),
)
FIELD_MAP = MapColors(
    (224, 213, 185), (55, 65, 60), (210, 199, 171), (159, 161, 133),
    (175, 187, 148), (126, 159, 151), (80, 111, 101), (249, 234, 200),
    (158, 157, 134), (155, 147, 136), (95, 87, 78),
)


def campus_atlas(bounds, size, scale, colors):
    """Plot the live world layout in the same projection as the map markers."""
    surface = pygame.Surface(size)
    surface.fill(colors.paper)
    origin = pygame.Vector2(bounds.topleft)

    def pixel(point):
        return (pygame.Vector2(point) * TILE - origin) * scale

    def polygon(feature, fill, edge, *, hatch=False):
        points = [pixel(point) for point in feature["points"]]
        area = pygame.draw.polygon(surface, fill, points)
        if hatch and area.width and area.height:
            mask = pygame.Surface(area.size, pygame.SRCALPHA)
            pygame.draw.polygon(mask, (255,255,255,255), [p-area.topleft for p in points])
            lines = pygame.Surface(area.size, pygame.SRCALPHA)
            for x in range(0,area.width+area.height,5):
                pygame.draw.line(lines,(*edge,92),(x,0),(x-area.height,area.height))
            lines.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(lines,area)
        pygame.draw.aalines(surface, edge, True, points)

    step = 10 * TILE
    for x in range(bounds.left // step * step, bounds.right, step):
        offset = round((x - bounds.left) * scale)
        pygame.draw.line(surface, colors.grid, (offset, 0), (offset, size[1]))
    for y in range(bounds.top // step * step, bounds.bottom, step):
        offset = round((y - bounds.top) * scale)
        pygame.draw.line(surface, colors.grid, (0, offset), (size[0], offset))
    # Decorative curves around the edges of the paper have no collision meaning.
    for index in range(7):
        shift = index * 3
        for base, phase in ((22, .6), (155, -1.8)):
            points = [pixel((x, base + shift + 13 * math.sin(x * .039 + phase)))
                      for x in range(0, 161, 4)]
            pygame.draw.aalines(surface, colors.contour, False, points)

    for feature in LANDSCAPES:
        polygon(feature, colors.grass, colors.contour)
    for spec in SPORTS_FIELDS:
        rect = pygame.Rect(pixel((spec.x, spec.y)), (spec.w*TILE*scale, spec.h*TILE*scale))
        pygame.draw.rect(surface, colors.grass, rect, border_radius=12)
        pygame.draw.rect(surface, colors.contour, rect.inflate(-8, -8), 1, border_radius=9)

    features = [(road, [pixel(p) for p in road["points"]]) for road in ROADS + WALKWAYS]
    for edge in (True, False):
        for road, points in features:
            width = max(1, round(road["width"] * TILE * scale * .77))
            pygame.draw.lines(surface, colors.curb if edge else colors.road, road.get("closed", False),
                              points, width + 2 if edge else width)
    for feature in WATERS:
        polygon(feature, colors.water, colors.shore, hatch=True)
    for feature in ISLANDS:
        polygon(feature, colors.grass, colors.shore)
    for road, points in features:
        if road.get("bridge"):
            pygame.draw.lines(surface, colors.road, False, points, max(1, round(TILE * scale * .6)))
    for building in BUILDINGS:
        spec = building["rect"]
        rect = pygame.Rect(pixel((spec.x, spec.y)), (spec.w*TILE*scale, spec.h*TILE*scale))
        pygame.draw.rect(surface, colors.curb, rect.move(1, 2), border_radius=2)
        pygame.draw.rect(surface, colors.building, rect, border_radius=2)
        pygame.draw.rect(surface, colors.outline, rect, 1, border_radius=2)
    return surface


def cut_panel(target, rect, fill=PANEL, border=LINE, corner=7):
    rect = pygame.Rect(rect)
    x,y = rect.topleft
    right,bottom = rect.right-1,rect.bottom-1
    corner = max(0, min(corner, rect.width//3, rect.height//3))
    if not corner:
        pygame.draw.rect(target,fill,rect)
        pygame.draw.rect(target,border,rect,1)
        return
    points = ((x,y),(right-corner,y),(right,y+corner),(right,bottom),
              (x+corner,bottom),(x,bottom-corner))
    pygame.draw.polygon(target,fill,points)
    pygame.draw.lines(target,border,True,points)


def icon(target, name, center, color, size=18):
    cx,cy=center
    s=size/20
    def p(x,y):
        return round(cx+x*s),round(cy+y*s)
    def strokes(points,width=2):
        pygame.draw.lines(target,color,False,[p(*point) for point in points],width)
    if name == "start":
        pygame.draw.polygon(target,color,[p(-5,-8),p(8,0),p(-5,8)])
    elif name == "resume":
        pygame.draw.arc(target,color,(cx-size*.42,cy-size*.42,size*.84,size*.84),
                        .12,5.50,2)
        pygame.draw.polygon(target,color,[p(-11,-1),p(-3,-1),p(-7,-7)])
    elif name == "settings":
        for y,at in ((-6,-3),(0,4),(6,0)):
            strokes(((-8,y),(8,y)),1)
            pygame.draw.circle(target,color,p(at,y),max(2,round(s*2)))
    elif name == "quit":
        strokes(((-1,-8),(-7,-8),(-7,8),(-1,8)))
        strokes(((-4,0),(8,0)))
        strokes(((3,-5),(8,0),(3,5)))
    elif name == "player":
        pygame.draw.circle(target,color,(cx,cy),max(2,round(size*.31)),2)
        pygame.draw.circle(target,color,(cx,cy),2)
    elif name == "goal":
        pygame.draw.polygon(target,color,[p(0,-7),p(7,0),p(0,7),p(-7,0)],2)
    elif name == "waypoint":
        pygame.draw.circle(target,color,(cx,cy),max(2,round(size*.31)),2)
    elif name == "campus":
        strokes(((-9,-3),(0,-9),(9,-3),(-9,-3)),1)
        for x in (-6,0,6):
            strokes(((x,0),(x,7)),1)
        strokes(((-9,8),(9,8)),1)
    elif name == "rain":
        strokes(((-8,-2),(-5,-5),(-2,-4),(0,-7),(5,-6),(8,-3),(7,0),(-8,0),(-8,-2)),1)
        for x in (-5,0,5):
            strokes(((x,3),(x-2,7)),1)
    elif name == "lock":
        strokes(((-4,-4),(-4,-7),(4,-7),(4,-4)),1)
        pygame.draw.rect(target,color,pygame.Rect(p(-6,-3),(round(12*s),round(10*s))),1,border_radius=2)
    elif name == "side":
        strokes(((-6,6),(-6,-6),(1,-6),(1,6),(-6,6)),1)
        strokes(((0,1),(8,1),(5,-2)),1)
    elif name == "sighting":
        strokes(((0,-8),(8,6),(-8,6),(0,-8)),1)
        strokes(((0,-3),(0,0)),1)
        pygame.draw.circle(target,color,p(0,3),1)


class InterfaceArt:
    def __init__(self):
        self.backdrop = self.encounter_art = None
        try:
            path = ROOT / "assets" / "ui" / "night-campus.jpg"
            source = pygame.image.load(path).convert()
        except (FileNotFoundError, pygame.error):
            source = None
        if source:
            width,height = WINDOW_SIZE
            scale = max(width/source.get_width(),height/source.get_height())
            fit = pygame.transform.smoothscale(source,(round(source.get_width()*scale),
                                                       round(source.get_height()*scale)))
            self.backdrop = pygame.Surface(WINDOW_SIZE)
            self.backdrop.blit(fit,fit.get_rect(center=(width//2,height//2)))
            crop = source.subsurface((source.get_width()*55//100, source.get_height()*16//100,
                                      source.get_width()*35//100, source.get_height()*78//100))
            self.encounter_art = pygame.transform.smoothscale(crop, (432, 500))
        self.encounter_shade = pygame.Surface((432, 500), pygame.SRCALPHA)
        for y in range(self.encounter_shade.get_height()):
            alpha = 24 + round(217*(y/(self.encounter_shade.get_height()-1))**3)
            pygame.draw.line(self.encounter_shade,(8,17,16,alpha),(0,y),(432,y))
        self.title_shade = pygame.Surface(WINDOW_SIZE,pygame.SRCALPHA)
        for x in range(WINDOW_SIZE[0]):
            opacity = round(11+224*max(0,1-x/1090)**1.3)
            pygame.draw.line(self.title_shade,(9,19,17,opacity),(x,0),(x,WINDOW_SIZE[1]))
        footer = pygame.Surface((WINDOW_SIZE[0],100),pygame.SRCALPHA)
        for y in range(100):
            alpha = round(141*(y/99)**1.5)
            pygame.draw.line(footer,(9,15,22,alpha),(0,y),(WINDOW_SIZE[0],y))
        self.title_shade.blit(footer,(0,WINDOW_SIZE[1]-100))
        self.mono_fonts = {}
        self.serif_fonts = {}

    def mono(self,target,text,point,size,color=PAPER,anchor="topleft"):
        if size not in self.mono_fonts:
            self.mono_fonts[size] = pygame.font.SysFont("consolas",size)
        label = self.mono_fonts[size].render(str(text),True,color)
        rect = label.get_rect()
        setattr(rect,anchor,point)
        target.blit(label,rect)
        return rect

    def heading(self, target, text, point, size, width, language, color=PAPER):
        family = ("georgia" if language == "en" else
                  "notoseriftc,pmingliu,mingliu,microsoftjhenghei")
        while size >= 11:
            key = (family,size)
            if key not in self.serif_fonts:
                self.serif_fonts[key] = pygame.font.SysFont(family,size,bold=True)
            font = self.serif_fonts[key]
            if font.size(text)[0] <= width or size == 11:
                label = font.render(text,True,color)
                return target.blit(label,point)
            size -= 1

    def keycap(self,target,key,rect,*,selected=False):
        rect = pygame.Rect(rect)
        cut_panel(target,rect,(57,44,33) if selected else (35,47,43),
                  GOLD if selected else LINE,3)
        self.mono(target,key,rect.center,14,GOLD if selected else PAPER,"center")
