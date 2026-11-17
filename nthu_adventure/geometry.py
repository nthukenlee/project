"""Shared drawing/collision geometry for referenced roads and lake shorelines."""
from __future__ import annotations
import pygame
from .constants import TILE


def pixel_points(points):
    # Geometry uses grid coordinates, not actor tile centers.
    return [pygame.Vector2(x*TILE, y*TILE) for x,y in points]


def smooth_path(points, closed=False, alpha=0.5, spacing=4.0):
    """Create a centripetal Catmull–Rom path from pixel-space control points."""
    vertices = [pygame.Vector2(point) for point in points]
    if len(vertices) < 3:
        return vertices
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")
    if spacing <= 0:
        raise ValueError("spacing must be positive")

    if closed:
        control = [vertices[-1], *vertices, vertices[0], vertices[1]]
    else:
        # Reflect the endpoints so the road leaves its first and last node
        # with a tangent based on the adjacent segment.
        control = [
            2 * vertices[0] - vertices[1],
            *vertices,
            2 * vertices[-1] - vertices[-2],
        ]

    def parameter(t, a, b):
        return t + max(a.distance_to(b), 1e-6) ** alpha

    result = []
    for index in range(len(control) - 3):
        p0, p1, p2, p3 = control[index:index + 4]
        t0 = 0.0
        t1 = parameter(t0, p0, p1)
        t2 = parameter(t1, p1, p2)
        t3 = parameter(t2, p2, p3)
        steps = max(2, round(p1.distance_to(p2) / spacing))
        for step in range(steps):
            t = t1 + (t2 - t1) * step / steps
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            result.append(
                b1 * ((t2 - t) / (t2 - t1))
                + b2 * ((t - t1) / (t2 - t1))
            )
    if not closed:
        result.append(vertices[-1])
    return result


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


def stroke(surface, color, points, width, end_caps=True, closed=False):
    width = max(1,round(width))
    vertices = [pygame.Vector2(x,y) for x,y in points]
    if len(vertices)<2: return
    if closed and vertices[-1] == vertices[0]:
        vertices.pop()
    rounded=[(round(point.x),round(point.y)) for point in vertices]
    pygame.draw.lines(surface, color, closed, rounded, width)
    if end_caps or closed:
        radius=max(1,width//2)
        for point in rounded:
            pygame.draw.circle(surface,color,point,radius)


def distance_to_path(position, points):
    point = pygame.Vector2(position)
    distance = float('inf')
    for a,b in zip(points, points[1:]):
        a,b = pygame.Vector2(a),pygame.Vector2(b)
        segment = b-a
        fraction = max(0,min(1,(point-a).dot(segment)/segment.length_squared())) if segment.length_squared() else 0
        distance = min(distance,point.distance_to(a+segment*fraction))
    return distance
