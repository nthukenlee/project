"""Rules and persistent state for the single campus survival adventure."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
from random import Random, SystemRandom
import shutil
import time

import pygame
from pygame import Vector2

from .constants import APP_FOLDER, WORLD_HEIGHT, WORLD_WIDTH
from .content import BUILDINGS, ROADS, WALKWAYS, SPAWN_TILE, tile_center
from .expedition import (
    ENEMY_SPEED, MAIN_STEPS, MINUTE_SECONDS, OUTBREAK_SITES, OUTDOOR_CLUES, ROOM_EVENTS,
    SIGNAL_MINUTE, START_MINUTE, STOP_MINUTE, STORY_STEPS, Encounter, choose_events, main_route,
    outbreak_site, valid_route,
)

ENDING = "last_name"
STORY_ROOMS = ("education", "main_library", "xin_hall")
LOCATIONS = tuple(ROOM_EVENTS)
CAMPUS_BUILDINGS = {b["id"]: b for b in BUILDINGS}
GEAR = ("food", "water", "bat", "lamp", "cell", "bike")
LEGACY_EVIDENCE = ("evacuation", "recording", "playback", "dispatch")
OBSERVATIONS = ("storm", "lawn", "exhibit", *STORY_STEPS)
STYLE_LIMITS = {"skin": 4, "hair_style": 4, "hair_color": 5, "shirt": 6, "gender": 2}
APPEARANCE = {"skin": 1, "hair_style": 0, "hair_color": 0, "shirt": 0, "gender": 0}
FACING = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
KINDS = {
    "wanderer": (66, 162, .55, (171, 134, 93)),
    "hunter": (110, 210, .47, (213, 102, 71)),
    "caller": (74, 195, .68, (200, 164, 95)),
    "mimic": (91, 150, .76, (153, 157, 196)),
    "armored": (55, 125, .92, (124, 166, 161)),
    "crawler": (117, 125, .60, (179, 147, 185)),
    "brute": (56, 152, 1.05, (202, 146, 110)),
}
MUTATIONS = ("crawler", "brute")
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


@dataclass
class Profile:
    language: str = "zh_TW"
    fullscreen: bool = False
    sound: bool = True
    scares: bool = True
    name: str = ""
    appearance: dict = field(default_factory=lambda: APPEARANCE.copy())

    def __post_init__(self):
        self.appearance = {
            key: max(0, min(STYLE_LIMITS[key] - 1, value))
            for key, default in APPEARANCE.items()
            for value in (self.appearance.get(key, default),)
        }


@dataclass
class Actor:
    kind: str
    position: tuple
    area: str = "campus"
    status: str = "waiting"
    health: int = 4
    facing: str = "down"
    moving: bool = False
    windup: float = 0
    target: str = ""
    cooldown: float = 0
    chasing: bool = False
    alerted: float = 0
    infection: float = 0
    choice: str = ""
    carried: bool = False
    home: tuple = ()
    identity: int = -1
    last_seen: tuple = ()
    linger: float = 0
    spawn_delay: float = 0
    entry_delay: float = 0
    stride: float = 0

    def __post_init__(self):
        if not self.home:
            self.home = self.position

    @property
    def infected(self):
        return self.status != "disguised" and (self.kind in KINDS or self.status == "turned")


@dataclass
class Cache:
    id: str
    area: str
    position: tuple
    item: str
    taken: bool = False
    container: str = "cabinet"


@dataclass
class Run:
    seed: int
    position: tuple
    area: str = "campus"
    facing: str = "down"
    elapsed: float = 0
    intro: bool = True
    observations: list = field(default_factory=list)
    pack: dict = field(default_factory=lambda: dict.fromkeys(GEAR, 0))
    hunger: float = 100
    thirst: float = 100
    battery: float = 0
    lamp_on: bool = False
    riding: bool = False
    selected: int = 0
    trail: list = field(default_factory=list)
    actors: dict[str, Actor] = field(default_factory=dict)
    caches: list[Cache] = field(default_factory=list)
    supply_layout: int = 0
    encounters: dict[str, Encounter] = field(default_factory=dict)
    outbreak: bool = False
    outbreak_at: float = -1
    blackout: bool = False
    storm_until: float = 0
    shortcuts: list[str] = field(default_factory=list)
    latched: dict[str, float] = field(default_factory=dict)
    lure_area: str = ""
    lure_point: tuple = ()
    lure_until: float = 0
    heard_event: str = ""
    heard_voice: str = "female"
    route: dict[str, str] = field(default_factory=dict)
    incident_site: str = ""
    ending: str | None = None
    death: str | None = None

    def __post_init__(self):
        if not valid_route(self.route):
            self.route = main_route(self.seed)
        if self.incident_site not in OUTBREAK_SITES:
            self.incident_site = outbreak_site(self.seed)

    def observe(self, key):
        if key in OBSERVATIONS + LEGACY_EVIDENCE and key not in self.observations:
            self.observations.append(key)

    @property
    def minute(self):
        return START_MINUTE + int(self.elapsed / MINUTE_SECONDS)

    @property
    def clock(self):
        hour, minute = divmod(self.minute % 1440, 60)
        return f"{hour:02d}:{minute:02d}"

    def start_outbreak(self):
        if self.outbreak_at >= 0:
            return
        self.outbreak = self.blackout = True
        self.outbreak_at = self.elapsed
        self.release_infected()
        for actor in self.actors.values():
            if actor.status == "passing":
                actor.status = "gone"

    def release_infected(self):
        if self.outbreak_at < 0:
            return
        for actor in self.actors.values():
            if actor.status == "dormant" and self.elapsed - self.outbreak_at >= actor.spawn_delay:
                actor.status = "hostile"

    @property
    def weather(self):
        if self.elapsed < self.storm_until or "lock_log" in self.observations or "playback" in self.observations or self.elapsed > 260:
            return "rain"
        return "cloud" if self.elapsed < 100 else "clear"

    @property
    def night(self):
        return "playback" in self.observations or self.blackout

    @property
    def team(self):
        return [key for key, actor in self.actors.items() if actor.status in ("joined", "bitten") and actor.choice in ("join", "trust", "escort")]

    @property
    def goal(self):
        return next((clue for clue in self.route if clue not in self.observations), MAIN_STEPS[-1])

    @property
    def goal_area(self):
        return self.route[self.goal]

    def alternate_clue_site(self):
        if len(self.route) == len(MAIN_STEPS):
            return None
        checkpoint = tuple(self.route)[2]
        current = self.route[checkpoint]
        occupied = set(self.route.values())
        if current in ROOM_EVENTS:
            candidates = OUTDOOR_CLUES.keys() - occupied
        elif (occupied - {current}) & OUTDOOR_CLUES.keys():
            candidates = ROOM_EVENTS.keys() - occupied
        else:
            candidates = OUTDOOR_CLUES.keys() - occupied
        return Random(f"backup-route/{self.seed}").choice(sorted(candidates))

    def spend_time(self, seconds):
        self.elapsed += seconds
        self.hunger = max(0, self.hunger - seconds * .155)
        self.thirst = max(0, self.thirst - seconds * .225)

    def add_gear(self, item):
        self.pack[item] += 1
        if item == "lamp" and self.battery <= 0:
            self.battery = 85

    @classmethod
    def read(cls, payload):
        state = cls(**payload)
        state.actors = {key: Actor(**value) for key, value in state.actors.items()}
        state.caches = [Cache(**value) for value in state.caches]
        state.encounters = {key: Encounter(**value) for key, value in state.encounters.items()}
        state.encounters = choose_events(state.seed, state.encounters)
        if not state.outbreak:
            state.actors = {
                key: actor for key, actor in state.actors.items()
                if not key.startswith("enc_") or actor.status not in ("waiting", "disguised")
            }
        if state.outbreak and state.outbreak_at < 0:
            state.outbreak_at = state.elapsed
        if "outbreak" not in payload:
            state.blackout = state.minute >= STOP_MINUTE
            if "playback" in state.observations or state.minute >= SIGNAL_MINUTE:
                state.start_outbreak()
            else:
                for actor in state.actors.values():
                    if actor.status == "hostile":
                        actor.status = "dormant"
        if state.area not in ("campus", *LOCATIONS) or not 0 <= state.selected < len(GEAR):
            raise ValueError("invalid travel state")
        if len(state.position) != 2 or not all(math.isfinite(v) for v in state.position):
            raise ValueError("invalid player position")
        if state.pack.keys() != set(GEAR):
            raise ValueError("invalid inventory")
        return state


class RunStore:
    def __init__(self, directory=None):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_FOLDER
        self.directory = Path(directory) if directory is not None else base / "last-report"
        self.directory.mkdir(parents=True, exist_ok=True)
        if directory is None:
            self.backup_legacy(base)

    def backup_legacy(self, base):
        for name in ("autosave", "slot_1", "slot_2", "slot_3"):
            original = base / f"{name}.json"
            backup = self.directory / f"legacy-{name}.json"
            if original.is_file() and not backup.exists():
                shutil.copy2(original, backup)

    def write(self, name, body):
        target = self.directory / f"{name}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 1, "data": body}, ensure_ascii=False), encoding="utf-8")
        for attempt in range(4):
            try:
                temporary.replace(target)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(.025 * (attempt + 1))

    def read(self, name, decode):
        target = self.directory / f"{name}.json"
        try:
            envelope = json.loads(target.read_text(encoding="utf-8"))
            if envelope["version"] != 1:
                raise ValueError("unknown format")
            return decode(envelope["data"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            backup = target.with_suffix(f".corrupt-{time.time_ns()}.json")
            if target.exists():
                target.replace(backup)
            return None

    def save(self, run):
        self.write("run", {"closed": run.death or run.ending} if run.death or run.ending else asdict(run))

    def load(self):
        return self.read("run", lambda data: None if data.get("closed") else Run.read(data))

    def profile(self):
        return self.read("profile", lambda data: Profile(**data)) or Profile()


def body(point):
    return pygame.Rect(round(point[0] - 8), round(point[1] - 6), 16, 12)


def move(point, displacement, collides):
    pos = Vector2(point)
    steps = max(1, math.ceil(displacement.length() / 5))
    dx, dy = displacement / steps
    for _ in range(steps):
        if not collides(body((pos.x + dx, pos.y))):
            pos.x += dx
        if not collides(body((pos.x, pos.y + dy))):
            pos.y += dy
    return pos


def visible(a, b, collides):
    start, delta = Vector2(a), Vector2(b) - a
    n = max(1, math.ceil(delta.length() / 10))
    return all(not collides(body(start + delta * (i / n))) for i in range(1, n + 1))


def facing(vector):
    x, y = vector
    if abs(x) > abs(y):
        return "right" if x > 0 else "left"
    return "down" if y > 0 else "up"


def distance(a, b):
    return Vector2(a).distance_to(b)


class CampusSlots:
    """Use the existing collision geometry to find connected, protected spawn cells."""
    def __init__(self, world, rooms):
        self.world = world
        self.start = tile_center(SPAWN_TILE)
        self.doors = {key: world.door(CAMPUS_BUILDINGS[key]) for key in LOCATIONS}
        self.reachable = self.connected()
        self.side_exits = {}
        for key in ("general_2", "engineering_1", "engineering_2", "chemistry", "gym"):
            footprint = pygame.Rect(CAMPUS_BUILDINGS[key]["rect"].pixels())
            self.side_exits[key] = self.near((footprint.right + 45, footprint.centery))
        self.path_points = [
            Vector2(x * 32, y * 32)
            for road in ROADS + WALKWAYS
            for x, y in road["points"]
        ]
        self.lawn = self.near((122 * 32, 57 * 32))
        self.lake = self.near((95 * 32, 84 * 32))
        self.incidents = {
            key: self.near(Vector2(tile) * 32)
            for key, tile in {
                "lake": (105, 75), "lawn": (125, 55), "clock": (107, 71), "plaza": (106, 64),
            }.items()
        }
        self.outdoor_clues = {key: self.near(Vector2(tile) * 32) for key, tile in OUTDOOR_CLUES.items()}
        passer_tiles = ((139,43), (133,48), (126,54), (117,64), (94,79))
        self.passer_points = [self.near(Vector2(tile) * 32) for tile in passer_tiles]
        self.containers = {key: self.room_containers(room) for key, room in rooms.items()}
        self.enemies = self.enemy_groups()

    def connected(self):
        start = tuple(round(v / 16) * 16 for v in self.start)
        return self.walkable_cells(start, 16, self.world.collides)

    @staticmethod
    def walkable_cells(start, step, collides):
        queue = deque([start])
        seen = {start}
        walkable = []
        while queue:
            x, y = queue.popleft()
            if collides(body((x, y))):
                continue
            walkable.append((x, y))
            for dx, dy in DIRECTIONS:
                neighbor = (x + dx * step, y + dy * step)
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return walkable

    def near(self, point):
        closest = min(self.reachable, key=Vector2(point).distance_squared_to)
        if not self.world.collides(body(point)) and visible(closest, point, self.world.collides):
            return tuple(point)
        return closest

    def room_containers(self, room):
        reachable = self.walkable_cells(room.entry, 12, room.hit)
        reserved = [room.story_point, room.event_point, *(fixture.point for fixture in room.fixtures)]
        spots = []
        for furniture, kind in room.storage:
            # Search from beside the furniture, with the player box outside it.
            for point in ((furniture.centerx, furniture.bottom + 14),
                          (furniture.right + 15, furniture.centery),
                          (furniture.left - 15, furniture.centery),
                          (furniture.centerx, furniture.top - 10)):
                if room.hit(body(point)) or any(distance(point, other) < 30 for other in reserved):
                    continue
                near = min(reachable, key=Vector2(point).distance_squared_to)
                if distance(point, near) <= 17 and visible(near, point, room.hit):
                    spots.append((point, kind))
                    reserved.append(point)
                    break
        return spots

    def place_supplies(self, run):
        rng = Random(f"stocked-rooms/{run.seed}")
        starts = sorted(self.containers, key=lambda key: distance(self.doors[key], self.start))[:3]
        early = ["water", "food", "lamp", "bat"]
        rng.shuffle(early)
        rooms = [key for key in self.containers if key not in starts]
        rng.shuffle(rooms)
        staples = ["water", "food"] * 10
        rng.shuffle(staples)
        extras = ["water"] * 7 + ["food"] * 6 + ["cell"] * 6 + ["bat"] * 2 + ["bike"]
        rng.shuffle(extras)
        caches = []
        for key in [*starts, *rooms]:
            spots = self.containers[key]
            picked = rng.sample(spots, min(3, len(spots)))
            for index, (point, container) in enumerate(picked):
                if key in starts and early:
                    item = early.pop()
                elif index == 0:
                    item = staples.pop()
                else:
                    item = ""
                caches.append(Cache(f"{key}/{index}", key, point, item, container=container))
        # Fill a second group of drawers across the campus instead of exhausting the pool
        # in the first few buildings iterated.
        spare = [cache for cache in caches if not cache.item]
        rng.shuffle(spare)
        for cache, item in zip(spare, extras):
            cache.item = item
        bat_point = (51 * 32 + 16, 42 * 32 + 16)
        caches.append(Cache("campus/materials_lab_court/bat", "campus", bat_point, "bat", container="ground"))
        return caches

    def restore_supplies(self, run):
        if run.supply_layout >= 2:
            if not any(cache.id == "campus/materials_lab_court/bat" for cache in run.caches):
                bat_point = (51 * 32 + 16, 42 * 32 + 16)
                run.caches.append(Cache("campus/materials_lab_court/bat", "campus", bat_point, "bat", container="ground"))
            return
        previously_opened = {(cache.area, tuple(cache.position)) for cache in run.caches if cache.taken}
        consumed = Counter(cache.item for cache in run.caches if cache.taken and cache.item)
        run.caches = self.place_supplies(run)
        for cache in sorted(run.caches, key=lambda cache: (cache.area, tuple(cache.position)) not in previously_opened):
            if consumed[cache.item]:
                consumed[cache.item] -= 1
                cache.taken = True
        run.supply_layout = 2

    def enemy_groups(self):
        protected = [self.start, *self.doors.values(), *self.incidents.values()]
        groups = []
        for x1, y1, x2, y2 in ((82, 42, 136, 69), (78, 65, 140, 98), (76, 93, 138, 127)):
            groups.append([
                point for point in self.reachable
                if x1*32 <= point[0] < x2*32 and y1*32 <= point[1] < y2*32
                and all(distance(point, safe) >= (400 if safe == self.start else 144) for safe in protected)
                and any(Vector2(point).distance_squared_to(node) <= 200**2 for node in self.path_points)
            ])
        return groups

    def restore_mutations(self, run):
        if any(key.startswith("mutation_") for key in run.actors):
            return
        mutant_rng = Random(f"late-mutations/{run.seed}")
        candidates = [*self.enemies[1], *self.enemies[2]]
        mutant_rng.shuffle(candidates)
        occupied = [actor.position for actor in run.actors.values() if actor.infected and actor.area == "campus"]
        late_types = [*MUTATIONS]
        if mutant_rng.random() < .5:
            late_types.append(mutant_rng.choice(MUTATIONS))
        mutant_rng.shuffle(late_types)
        for index, kind in enumerate(late_types):
            point = next((point for point in candidates if all(distance(point, other) >= 125 for other in occupied)), None)
            if point is None:
                break
            occupied.append(point)
            run.actors[f"mutation_{index}"] = Actor(kind, point, status="dormant",
                                                     spawn_delay=72 + index * 18 + mutant_rng.randint(0, 9))

    def new(self, seed=None):
        seed = SystemRandom().getrandbits(63) if seed is None else seed
        rng = Random(seed)
        run = Run(seed, self.start, encounters=choose_events(seed))
        self.restore_supplies(run)
        kinds = [kind for kind in KINDS if kind not in MUTATIONS] * 6
        rng.shuffle(kinds)
        for group in self.enemies:
            selected = []
            candidates = group.copy()
            rng.shuffle(candidates)
            for point in candidates:
                if all(distance(point, other) >= 125 for other in selected):
                    selected.append(point)
                    enemy_id = f"enemy_{len(run.actors)}"
                    run.actors[enemy_id] = Actor(kinds.pop(), point, status="dormant", spawn_delay=((len(selected)-1) % 3) * 10)
                    if len(selected) == 10:
                        break
        self.restore_mutations(run)
        run.actors.update({
            "student": Actor("student", (530, 350), "education"),
            "clerk": Actor("clerk", (1010, 342), "main_library"),
            "stranger": Actor("stranger", self.lake),
        })
        for i, point in enumerate(self.passer_points):
            run.actors[f"passer_{i}"] = Actor("student", point, status="passing", identity=i)
        return run


def nearby_targets(run, area):
    return [
        (key, actor) for key, actor in run.actors.items()
        if actor.area == area and actor.status not in ("gone", "dormant") and actor.entry_delay <= 0
    ]


def use_gear(run, item, collides):
    if not run.pack[item]:
        return "empty"
    if item in ("food", "water"):
        field_name = "hunger" if item == "food" else "thirst"
        need = getattr(run, field_name)
        if need > 94:
            return "full"
        setattr(run, field_name, min(100, need + (38 if item == "food" else 46)))
        run.pack[item] -= 1
    elif item == "lamp":
        if run.battery <= 0:
            return "empty_battery"
        run.lamp_on = not run.lamp_on
    elif item == "cell":
        if not run.pack["lamp"] or run.battery > 85:
            return "no_charge"
        run.battery = min(100, run.battery + 58)
        run.pack[item] -= 1
    elif item == "bike":
        if run.area != "campus":
            return "bike_outside"
        run.riding = not run.riding
    else:
        direction = Vector2(FACING[run.facing])
        for _, enemy in nearby_targets(run, run.area):
            if not enemy.infected:
                continue
            delta = Vector2(enemy.position) - run.position
            if delta.length_squared() < 175**2:
                enemy.alerted = 4
                enemy.chasing = True
            if delta.length_squared() <= 82**2 and delta.dot(direction) >= -5 and visible(run.position, enemy.position, collides):
                enemy.windup = 0
                enemy.cooldown = .95
                force = {"armored": 28, "brute": 16}.get(enemy.kind, 68)
                enemy.position = tuple(move(enemy.position, direction * force, collides))
                enemy.health = max(0, enemy.health - 1)
                if enemy.health == 0:
                    enemy.status = "gone"
                    enemy.chasing = False
    return f"used_{item}"


def follow(actor, target, speed, dt, collides):
    start = Vector2(actor.position)
    delta = Vector2(target) - start
    if delta.length_squared() < 1:
        actor.moving = False
        return
    stride = delta.normalize() * min(speed * dt, delta.length())
    direct = move(start, stride, collides)
    travel = direct.distance_to(start)
    actor.moving = travel > .06
    if actor.moving:
        offset = direct - start
        previous = Vector2(FACING[actor.facing])
        if previous.dot(offset) < travel * .48:
            actor.facing = facing(offset)
        actor.stride = (actor.stride + travel) % 4800
    actor.position = tuple(direct)


def change_area(run, area, point, collides):
    if run.area == area:
        return
    for i, key in enumerate(run.team):
        companion = run.actors[key]
        if companion.choice == "escort" and (companion.area != run.area or
                                             distance(companion.position, run.position) > 128):
            continue
        companion.area = area
        for dx, dy in ((0, -1), (1, 0), (-1, 0), (0, 1)):
            offset = Vector2(point) + Vector2(dx, dy) * (25 + i * 23)
            if not collides(body(offset)) and visible(point, offset, collides):
                break
        else:
            offset = point
        companion.position = tuple(offset)
    run.area, run.position = area, tuple(point)
    run.trail.clear()
    run.riding = False


def cross_door(run, area, source, destination, source_clear, destination_clear, door):
    """Move the player and any close pursuers that can see the same doorway."""
    pursuing = []
    if run.outbreak and run.latched.get(door, 0) <= run.elapsed:
        pursuing = sorted(
            (actor for _, actor in nearby_targets(run, run.area)
             if actor.infected and actor.chasing and actor.target in ("", "player")
             and distance(source, actor.position) <= 165 and visible(actor.position, source, source_clear)),
            key=lambda actor: distance(source, actor.position),
        )[:2]
    change_area(run, area, destination, destination_clear)
    remaining = []
    for index, enemy in enumerate(pursuing):
        # Arrive just behind the threshold from the player's point of view.
        angle = 1 if index % 2 else -1
        for offset in ((0, 38+index*18), (0, -38-index*18), (angle*44, 0), (-angle*44, 0)):
            arrival = Vector2(destination) + offset
            if not destination_clear(body(arrival)) and visible(destination, arrival, destination_clear):
                break
        else:
            continue
        enemy.area = area
        enemy.position = enemy.home = tuple(arrival)
        enemy.last_seen = tuple(destination)
        enemy.linger, enemy.alerted = 4., 7.
        enemy.windup, enemy.cooldown = 0., .6
        enemy.target = "player"
        enemy.moving = False
        enemy.entry_delay = 1.32 + index * .72
        remaining.append(enemy.kind)
    return remaining


def simulate(run, dt, direction, sprinting, collides):
    """Advance only during active gameplay. Output IDs for UI/audio events."""
    if run.death or run.ending:
        return []
    run.elapsed += dt
    run.release_infected()
    outdoors = run.area == "campus"
    exertion = 1.27 if sprinting and direction else 1
    run.hunger = max(0, run.hunger - dt * .155 * exertion)
    run.thirst = max(0, run.thirst - dt * .225 * exertion)
    if not run.hunger or not run.thirst:
        run.death = "hunger" if not run.hunger else "thirst"
        return [run.death]
    if run.lamp_on:
        run.battery = max(0, run.battery - dt * .78)
        run.lamp_on = run.battery > 0
    if direction:
        run.facing = facing(direction)
        speed = 268 if run.riding else 192 if sprinting else 132
        if outdoors and run.weather == "rain":
            speed *= .8
        run.position = tuple(move(run.position, direction.normalize() * speed * dt, collides))
    if not run.trail or distance(run.trail[-1], run.position) > 20:
        run.trail.append(run.position)
        del run.trail[:-45]
    notices = []
    for key, actor in run.actors.items():
        if actor.entry_delay > 0:
            actor.entry_delay = max(0., actor.entry_delay - dt)
            if not actor.entry_delay and actor.area == run.area:
                notices.append("door_breach/" + actor.kind)
        if actor.status not in ("passing", "joined", "bitten") and not actor.infected:
            actor.moving = False
        if actor.status != "bitten":
            continue
        actor.infection -= dt
        if actor.infection <= 0:
            actor.status = "turned"
            actor.cooldown = .75
            notices.append("turned")
        elif key in run.team and actor.area == run.area:
            follow(actor, run.position, 94, dt, collides)

    active = nearby_targets(run, run.area)
    for i, key in enumerate(run.team):
        actor = run.actors[key]
        if actor.status != "joined" or actor.area != run.area:
            continue
        if actor.carried and any(enemy.chasing and distance(enemy.position, actor.position) < 125
                                 for _, enemy in active if enemy.infected):
            actor.status = "gone"
            notices.append("betrayal_dynamic" if key.startswith("enc_") else "betrayal")
            continue
        if distance(actor.position, run.position) > 42 + i*30:
            target = run.position
            if not visible(actor.position, target, collides):
                target = next((point for point in reversed(run.trail)
                               if distance(actor.position, point) > 17 and visible(actor.position, point, collides)), actor.position)
            speed = 96 if actor.choice == "escort" else 238 if run.riding else 173
            follow(actor, target, speed, dt, collides)
        else:
            actor.moving = False

    for _, person in active:
        if person.status == "passing":
            # Use straight stretches with a pause at each end for a natural gait.
            phase = (run.elapsed + person.identity * .72) % 12
            if phase < 1.25 or 6 <= phase < 7.25:
                person.moving = False
                continue
            mark = Vector2(person.home) + (Vector2(45, 18) if phase < 6 else Vector2(-25, -10))
            if collides(body(mark)) or not visible(person.position, mark, collides):
                person.moving = False
            elif distance(person.position, run.position) < 580:
                follow(person, mark, 34, dt, collides)

    for _, enemy in active:
        if not enemy.infected:
            continue
        if distance(enemy.position, run.position) > 680:
            continue
        actors = {"player": run.position}
        actors.update({key: actor.position for key, actor in active if actor.status in ("joined", "waiting", "bitten") and not actor.infected})
        speed, sight, windup, _ = KINDS.get(enemy.kind, KINDS["wanderer"])
        enemy.cooldown = max(0, enemy.cooldown - dt)
        enemy.alerted = max(0, enemy.alerted - dt)
        if enemy.windup > 0:
            enemy.windup = max(0, enemy.windup-dt)
            if not enemy.windup:
                target = actors.get(enemy.target)
                reach = 59 if enemy.kind == "brute" else 45
                if target is not None and distance(enemy.position, target) < reach and visible(enemy.position, target, collides):
                    if enemy.target == "player":
                        run.death = "bite"
                        return notices + ["bite"]
                    victim = run.actors[enemy.target]
                    if victim.status != "bitten":
                        victim.status, victim.infection = "bitten", 8
                        notices.append("infected")
                enemy.cooldown = 1.1
            continue
        if (run.lure_area == run.area and run.elapsed < run.lure_until and
                distance(enemy.position, run.lure_point) < 255 and distance(enemy.position, run.position) > 57):
            enemy.target = ""
            enemy.chasing = False
            follow(enemy, run.lure_point, speed * ENEMY_SPEED, dt, collides)
            continue
        target_id = min(actors, key=lambda key: distance(enemy.position, actors[key]))
        target = actors[target_id]
        gap = distance(enemy.position, target)
        sound_sight = 95 if run.riding else 58 if sprinting else 0
        radius = sight + (120 if enemy.alerted else 0)
        if target_id == "player":
            radius += sound_sight + (48 if run.lamp_on else 0)
        was_chasing = enemy.chasing
        enemy.chasing = gap < radius and visible(enemy.position, target, collides)
        if enemy.chasing:
            enemy.target = target_id
            enemy.last_seen = target
            enemy.linger = 6 if enemy.kind == "mimic" else 2.8
        elif was_chasing and enemy.kind == "mimic":
            notices.append("mimic_wait")
        enemy.moving = False
        attack_range = 49 if enemy.kind == "brute" else 37
        if enemy.chasing and gap < attack_range and enemy.cooldown <= 0:
            enemy.target, enemy.windup = target_id, windup
            enemy.facing = facing(Vector2(target) - enemy.position)
            notices.append("warning")
        elif enemy.chasing and enemy.cooldown <= 0:
            if enemy.kind == "caller" and enemy.alerted == 0:
                for _, other in active:
                    if other.infected and distance(other.position, enemy.position) < 290:
                        other.alerted = 6
                notices.append("call")
            burst = 1.33 if enemy.kind == "hunter" and 46 < gap < 122 else 1
            if enemy.kind == "crawler" and 40 < gap < 85:
                burst = 1.23
            if outdoors and run.weather == "rain":
                speed *= .92
            follow(enemy, target, speed * burst * ENEMY_SPEED, dt, collides)
        elif not enemy.chasing and not enemy.cooldown:
            if enemy.linger > 0:
                enemy.linger = max(0, enemy.linger - dt)
                if enemy.kind != "mimic" and enemy.last_seen and distance(enemy.position, enemy.last_seen) > 26:
                    follow(enemy, enemy.last_seen, speed * .65 * ENEMY_SPEED, dt, collides)
                continue
            phase = run.elapsed * .46 + enemy.home[0] * .063
            patrol = Vector2(enemy.home) + Vector2(math.cos(phase), math.sin(phase)) * 39
            follow(enemy, patrol, 29 * ENEMY_SPEED, dt, collides)
    return notices
