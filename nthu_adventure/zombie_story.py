"""The Success Lake chapter and its outdoor encounters."""
from dataclasses import dataclass, field
import math

import pygame

from .content import tile_center


@dataclass(frozen=True)
class StoryStop:
    label: str
    tile: tuple[int, int]

    @property
    def position(self):
        return pygame.Vector2(tile_center(self.tile))


SHELTER = StoryStop("zombie.shelter", (91, 82))
LOGBOOK = StoryStop("zombie.logbook", (92, 89))
RELAY = StoryStop("zombie.relay", (96, 103))
OBJECTIVES = (SHELTER, LOGBOOK, RELAY, SHELTER)
FINISHED = len(OBJECTIVES)
SPAWNS = ((90, 91), (89, 96), (95, 101), (91, 106))
DETECT_RADIUS = 185
LOSE_RADIUS = 255
HOME_LEASH = 300
ATTACK_RADIUS = 40
ATTACK_WINDUP = 0.5
ATTACK_COOLDOWN = 1.25
HIT_DAMAGE = 20


def body_at(point):
    return pygame.Rect(round(point.x - 8), round(point.y - 6), 16, 13)


def clear_path(start, end, collides):
    steps = max(1, math.ceil(start.distance_to(end) / 8))
    return all(not collides(body_at(start.lerp(end, i / steps))) for i in range(1, steps + 1))


@dataclass
class Zombie:
    home: pygame.Vector2
    position: pygame.Vector2 = field(init=False)
    facing: str = "down"
    chasing: bool = False
    moving: bool = False
    windup: float = 0
    cooldown: float = 0

    def __post_init__(self):
        self.position = self.home.copy()

    def step(self, player, dt, collides):
        """Advance an encounter and return True only for a landed attack."""
        self.moving = False
        self.cooldown = max(0, self.cooldown - dt)
        distance = self.position.distance_to(player)
        if self.chasing:
            if distance > LOSE_RADIUS or player.distance_to(self.home) > HOME_LEASH:
                self.chasing = False
                self.windup = 0
        elif distance <= DETECT_RADIUS and player.distance_to(self.home) <= HOME_LEASH:
            self.chasing = clear_path(self.position, player, collides)

        if self.windup:
            self.windup = max(0, self.windup - dt)
            if self.windup == 0:
                self.cooldown = ATTACK_COOLDOWN
                return distance <= ATTACK_RADIUS and clear_path(self.position, player, collides)
            return False
        if self.chasing and distance <= ATTACK_RADIUS:
            if not self.cooldown and clear_path(self.position, player, collides):
                self.windup = ATTACK_WINDUP
            return False

        destination = player if self.chasing else self.home
        offset = destination - self.position
        if offset.length_squared() <= 1:
            return False
        move = offset.normalize() * min(offset.length(), (104 if self.chasing else 65) * dt)
        for delta in (move, pygame.Vector2(move.x, 0), pygame.Vector2(0, move.y)):
            candidate = self.position + delta
            if delta.length_squared() > 0 and not collides(body_at(candidate)):
                self.position = candidate
                self.moving = True
                if abs(delta.x) > abs(delta.y):
                    self.facing = "right" if delta.x > 0 else "left"
                else:
                    self.facing = "down" if delta.y > 0 else "up"
                break
        return False


class ZombieEncounter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.enemies = [Zombie(pygame.Vector2(tile_center(tile))) for tile in SPAWNS]
        self.immunity = 0

    def update(self, state, dt, collides, *, enabled=None):
        self.immunity = max(0, self.immunity - dt)
        if enabled is None:
            enabled = state.zombie_stage > 0
        if not enabled:
            return None
        player = pygame.Vector2(state.player_x, state.player_y)
        struck = False
        for enemy in self.enemies:
            if (
                enemy.step(player, dt, collides)
                and not self.immunity
                and player.distance_to(SHELTER.position) >= 80
            ):
                state.health = max(0, state.health - HIT_DAMAGE)
                self.immunity = 1.1
                struck = True
        if state.health == 0:
            state.player_x, state.player_y = SHELTER.position
            state.health = 100
            self.reset()
            return "zombie.rescued"
        return "zombie.hit" if struck else None
