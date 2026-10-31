"""Shared drawing/collision geometry for referenced roads and lake shorelines."""
from __future__ import annotations
import pygame
from .constants import TILE


def pixel_points(points):
    # Geometry uses grid coordinates, not actor tile centers.
    return [pygame.Vector2(x*TILE, y*TILE) for x,y in points]


def smooth_polygon(points, samples=6):
    """Closed Catmull–Rom shoreline; the same points feed rendering and collision."""
    vertices = pixel_points(points)
    result = []
    for index, p1 in enumerate(vertices):
        p0, p2, p3 = vertices[index-1], vertices[(index+1)%len(vertices)], vertices[(index+2)%len(vertices)]
        for step in range(samples):
            t = step/samples
            point = .5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
            result.append((round(point.x), round(point.y)))
    return result


def stroke(surface, color, points, width, end_caps=True):
    width = max(1,round(width))
    vertices = [(round(x),round(y)) for x,y in points]
    if len(vertices)<2: return
    pygame.draw.lines(surface, color, False, vertices, width)
    for i, point in enumerate(vertices):
        if not end_caps and (i == 0 or i == len(vertices) - 1):
            continue
        pygame.draw.circle(surface, color, point, max(1,width//2))


def distance_to_path(position, points):
    point = pygame.Vector2(position)
    distance = float('inf')
    for a,b in zip(points, points[1:]):
        a,b = pygame.Vector2(a),pygame.Vector2(b)
        segment = b-a
        fraction = max(0,min(1,(point-a).dot(segment)/segment.length_squared())) if segment.length_squared() else 0
        distance = min(distance,point.distance_to(a+segment*fraction))
    return distance
