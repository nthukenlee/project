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
GEAR = ("food", "water", "bat", "key", "bike")
OLD_GEAR = ("food", "water", "bat", "lamp", "cell", "bike")
LEGACY_EVIDENCE = ("evacuation", "recording", "playback", "dispatch")
OBSERVATIONS = ("storm", "lawn", "exhibit", *STORY_STEPS)
STYLE_LIMITS = {"skin": 4, "hair_style": 4, "hair_color": 5, "shirt": 6, "gender": 2}
APPEARANCE = {"skin": 1, "hair_style": 0, "hair_color": 0, "shirt": 0, "gender": 0}
FACING = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
KINDS = {
    "hunter": (110, 210, .47, (213, 102, 71)),
    "hidden": (98, 145, .62, (167, 166, 127)),
    "stalker": (91, 215, .65, (156, 149, 191)),
    "thrower": (68, 240, .76, (212, 157, 94)),
}
MUTATIONS = ("hidden", "thrower")
LEGACY_INFECTED = {"wanderer": "hunter", "caller": "thrower", "mimic": "hidden",
                   "armored": "stalker", "crawler": "hidden", "brute": "thrower"}
INFECTION_SECONDS = 5.5
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
    stunned: float = 0
    carried_key: bool = False
    concealed: bool = False
    reveal: float = 0
    throw_target: tuple = ()
    guard_door: str = ""

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
class Projectile:
    area: str
    position: tuple
    velocity: tuple
    contaminated: bool
    injury_roll: float
    infection_roll: float
    remaining: float = .85


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
    riding: bool = False
    stamina: float = 100
    exhausted: bool = False
    injury_until: float = 0
    infection_until: float = 0
    infection_cause: str = "bite"
    projectiles: list[Projectile] = field(default_factory=list)
    throws: int = 0
    locked: list[str] = field(default_factory=list)
    access_ready: bool = False
    event_progress: dict = field(default_factory=dict)
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
        return [key for key, actor in self.actors.items() if actor.status in ("joined", "bitten")
                and actor.choice in ("join", "trust", "escort", "lawn_fast", "lawn_slow")]

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
        if item in ("key", "bike", "bat"):
            self.pack[item] = 1
        else:
            self.pack[item] += 1

    @classmethod
    def read(cls, payload):
        payload = dict(payload)
        payload.pop("battery", None)
        payload.pop("lamp_on", None)
        if not isinstance(payload.get("pack"), dict):
            raise ValueError("invalid inventory")
        if "lamp" in payload["pack"] or "cell" in payload["pack"]:
            slot = payload.get("selected", 0)
            selected = OLD_GEAR[slot] if 0 <= slot < len(OLD_GEAR) else "food"
            payload["selected"] = GEAR.index(selected) if selected in GEAR else 0
            payload["pack"] = {item: payload["pack"].get(item, 0) for item in GEAR}
        state = cls(**payload)
        state.actors = {}
        for key, old_actor in payload.get("actors", {}).items():
            actor = dict(old_actor)
            actor.pop("health", None)
            actor["kind"] = LEGACY_INFECTED.get(actor["kind"], actor["kind"])
            if actor["status"] == "bitten":
                actor["infection"] = min(INFECTION_SECONDS, actor["infection"])
            state.actors[key] = Actor(**actor)
        state.caches = [Cache(**{**value, "item": "" if value["item"] in ("lamp", "cell") else value["item"]})
                        for value in state.caches]
        state.projectiles = [Projectile(**value) for value in state.projectiles]
        state.encounters = {key: Encounter(**value) for key, value in state.encounters.items()}
        state.encounters = choose_events(state.seed, state.encounters)
        current_actors = {event.actor_id for event in state.encounters.values()}
        state.actors = {key: actor for key, actor in state.actors.items()
                        if not key.startswith("enc_") or actor.status not in ("waiting", "disguised")
                        or key in current_actors}
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
        self.rooms = rooms
        self.start = tile_center(SPAWN_TILE)
        self.doors = {key: world.door(CAMPUS_BUILDINGS[key]) for key in LOCATIONS}
        self.reachable = self.connected()
        self.side_exits = {}
        self.side_entries = {}
        for key in ("general_2", "engineering_1", "engineering_2", "chemistry", "gym",
                    "education", "main_library", "xin_hall"):
            footprint = pygame.Rect(CAMPUS_BUILDINGS[key]["rect"].pixels())
            self.side_exits[key] = self.near((footprint.right + 45, footprint.centery))
            room = rooms[key]
            fixture = next((f.point for f in room.fixtures if f.key == "side_exit"), None)
            if fixture is None:
                cells = self.walkable_cells(room.entry, 20, room.hit)
                reserved = [room.story_point, room.event_point, *(f.point for f in room.fixtures)]
                fixture = max((p for p in cells if all(distance(p, spot) > 55 for spot in reserved)),
                              key=lambda p: p[0] + distance(p, room.entry) * .3)
            self.side_entries[key] = fixture
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
        self.start_rooms = sorted(self.containers, key=lambda key: distance(self.doors[key], self.start))[:3]
        self.event_points = {}
        self.rest_points = {}
        self.hidden_spots = {}
        for key, room in rooms.items():
            reserved = [room.entry, room.story_point, room.event_point, *(f.point for f in room.fixtures)]
            if key in self.side_entries:
                reserved.append(self.side_entries[key])
            self.hidden_spots[key] = [
                p for p in self.walkable_cells(room.entry, 30, room.hit)
                if all(distance(p, point) >= 112 for point in reserved)
            ]
        for key in ("general_4", "gym", "xin_hall"):
            room = rooms[key]
            cells = self.walkable_cells(room.entry, 16, room.hit)
            occupied = [room.story_point, room.event_point, *(f.point for f in room.fixtures),
                        *(point for point, _ in self.containers[key])]
            choices = [p for p in cells if all(distance(p, spot) >= 48 for spot in occupied)]
            near = min(choices, key=lambda p: distance(p, room.event_point))
            far = max(choices, key=lambda p: distance(p, near))
            self.event_points[key] = (near, far)
            self.rest_points[key] = near
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
        starts = self.start_rooms
        early = ["water", "food", "water", "bat"]
        rng.shuffle(early)
        rooms = [key for key in self.containers if key not in starts]
        rng.shuffle(rooms)
        staples = ["water", "food"] * 10
        rng.shuffle(staples)
        extras = ["water"] * 10 + ["food"] * 10 + ["bike"]
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
                                                     spawn_delay=32 + index * 12 + mutant_rng.randint(0, 5),
                                                     concealed=kind == "hidden")

    def restore_access(self, run):
        if run.access_ready:
            return
        rng = Random(f"campus-access/{run.seed}")
        lockable = sorted(set(self.doors) - set(self.start_rooms) - {run.area})
        run.locked = rng.sample(lockable, rng.randint(3, 5))
        available = [c for c in run.caches if c.area in self.doors and not c.taken and c.area not in run.locked]
        if available:
            candidate = rng.choice([c for c in available if not c.item] or available)
            displaced = candidate.item
            candidate.item = "key"
            if displaced:
                empty = [c for c in run.caches if c is not candidate and not c.item and not c.taken]
                if empty:
                    rng.choice(empty).item = displaced
        else:
            area = rng.choice(self.start_rooms)
            point, container = self.containers[area][0]
            run.caches.append(Cache("access/key", area, point, "key", container=container))
        if not run.pack["bike"] and not any(c.item == "bike" and not c.taken for c in run.caches):
            area = rng.choice(self.start_rooms)
            point, _ = self.containers[area][0]
            run.caches.append(Cache("access/bike", area, point, "bike", container="bike"))
        carriers = [actor for key, actor in run.actors.items()
                    if key.startswith("enemy_") and actor.status in ("dormant", "hostile")]
        for actor in rng.sample(carriers, min(3, len(carriers))):
            actor.carried_key = True
        for area in rng.sample(sorted(self.side_entries), 5):
            if rng.random() < .55:
                side = rng.choice((False, True))
                gate = area + ("/side" if side else "")
                point = self.side_exits[area] if side else tuple(self.doors[area])
                spot = self.near(Vector2(point) + (0, 32))
                run.actors[f"guard_{area}"] = Actor("stalker", spot, status="dormant",
                                                   spawn_delay=6, guard_door=gate)
        for index, area in enumerate(rng.sample(sorted(self.doors), 7)):
            candidates = self.hidden_spots[area]
            if candidates:
                run.actors[f"indoor_{area}"] = Actor("hidden", rng.choice(candidates), area,
                                                    status="dormant", spawn_delay=3 + index * 2,
                                                    concealed=True)
        run.access_ready = True

    def new(self, seed=None):
        seed = SystemRandom().getrandbits(63) if seed is None else seed
        rng = Random(seed)
        run = Run(seed, self.start, encounters=choose_events(seed))
        self.restore_supplies(run)
        kinds = (["hunter"] * 17 + ["hidden"] * 6 + ["stalker"] * 4 + ["thrower"] * 3)
        rng.shuffle(kinds)
        for group in self.enemies:
            selected = []
            candidates = group.copy()
            rng.shuffle(candidates)
            for point in candidates:
                if all(distance(point, other) >= 125 for other in selected):
                    selected.append(point)
                    enemy_id = f"enemy_{len(run.actors)}"
                    kind = kinds.pop()
                    run.actors[enemy_id] = Actor(kind, point, status="dormant",
                                                 spawn_delay=((len(selected)-1) % 3) * 5,
                                                 concealed=kind == "hidden")
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
        self.restore_access(run)
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
    elif item == "key":
        return "key_ready"
    elif item == "bike":
        if run.area != "campus":
            return "bike_outside"
        run.riding = not run.riding
    else:
        if run.stamina < 22:
            return "too_tired"
        run.stamina -= 22
        direction = Vector2(FACING[run.facing])
        for key, enemy in nearby_targets(run, run.area):
            if not enemy.infected:
                continue
            delta = Vector2(enemy.position) - run.position
            if delta.length_squared() < 175**2:
                enemy.alerted = 4
                enemy.chasing = True
            if delta.length_squared() <= 82**2 and delta.dot(direction) >= -5 and visible(run.position, enemy.position, collides):
                enemy.windup = 0
                enemy.throw_target = ()
                enemy.stunned = 1.65
                enemy.concealed = False
                enemy.chasing = False
                enemy.moving = False
                enemy.position = tuple(move(enemy.position, direction * 60, collides))
                if enemy.carried_key:
                    enemy.carried_key = False
                    run.caches.append(Cache(f"drop/{key}", run.area, enemy.position, "key", container="dropped_key"))
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
             if actor.infected and actor.chasing and not actor.stunned and not actor.concealed
             and actor.target in ("", "player")
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


def launch_projectile(run, enemy):
    aim = Vector2(enemy.throw_target) - enemy.position
    if not aim.length_squared():
        return
    rolls = Random(f"projectile/{run.seed}/{run.throws}")
    run.throws += 1
    run.projectiles.append(Projectile(run.area, enemy.position, tuple(aim.normalize() * 350),
                                      rolls.random() < .4, rolls.random(), rolls.random()))


def advance_projectiles(run, dt, collides):
    notices = []
    active = []
    for projectile in run.projectiles:
        step = min(projectile.remaining, dt)
        projectile.remaining -= dt
        if projectile.area != run.area:
            if projectile.remaining > 0:
                active.append(projectile)
            continue
        velocity = Vector2(projectile.velocity)
        start = Vector2(projectile.position)
        samples = max(1, math.ceil(velocity.length() * step / 6))
        for index in range(1, samples + 1):
            point = start + velocity * step * index / samples
            if collides(pygame.Rect(round(point.x) - 3, round(point.y) - 3, 6, 6)):
                break
            if distance(point, run.position) <= 15:
                if projectile.injury_roll < .35:
                    run.injury_until = max(run.injury_until, run.elapsed + 10)
                    notices.append("throw_injury")
                    if projectile.contaminated and projectile.infection_roll < .20:
                        run.infection_until = run.elapsed + 1.35
                        run.infection_cause = "contamination"
                        notices.append("throw_infected")
                else:
                    notices.append("throw_hit")
                break
        else:
            if projectile.remaining > 0:
                projectile.position = tuple(point)
                active.append(projectile)
    run.projectiles = active
    return notices


def simulate(run, dt, direction, sprinting, collides):
    """Advance only during active gameplay. Output IDs for UI/audio events."""
    if run.death or run.ending:
        return []
    run.elapsed += dt
    if run.infection_until:
        if run.elapsed >= run.infection_until:
            run.death = run.infection_cause
            return [run.death]
        return []
    run.release_infected()
    outdoors = run.area == "campus"
    if run.stamina < 8:
        run.exhausted = True
    elif run.stamina >= 27:
        run.exhausted = False
    sprinting = sprinting and not run.riding and not run.exhausted
    if sprinting and direction:
        run.stamina = max(0, run.stamina - dt * 17)
    else:
        run.stamina = min(100, run.stamina + dt * 11)
    exertion = 1.27 if sprinting and direction else 1
    run.hunger = max(0, run.hunger - dt * .155 * exertion)
    run.thirst = max(0, run.thirst - dt * .225 * exertion)
    if not run.hunger or not run.thirst:
        run.death = "hunger" if not run.hunger else "thirst"
        return [run.death]
    if direction:
        run.facing = facing(direction)
        speed = 268 if run.riding else 192 if sprinting else 132
        if outdoors and run.weather == "rain":
            speed *= .8
        if run.elapsed < run.injury_until:
            speed *= .8
        if "carrying_parcel" in run.event_progress:
            speed *= .78
        run.position = tuple(move(run.position, direction.normalize() * speed * dt, collides))
    if not run.trail or distance(run.trail[-1], run.position) > 20:
        run.trail.append(run.position)
        del run.trail[:-45]
    notices = advance_projectiles(run, dt, collides)
    if run.infection_until:
        return notices
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
            actor.kind = "hunter"
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
            speed = {"escort": 96, "lawn_slow": 112, "lawn_fast": 181}.get(
                actor.choice, 238 if run.riding else 173)
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
        speed, sight, windup, _ = KINDS.get(enemy.kind, KINDS["hunter"])
        if enemy.stunned > 0:
            enemy.stunned = max(0., enemy.stunned - dt)
            enemy.moving = False
            continue
        gap_to_player = distance(enemy.position, run.position)
        if enemy.concealed:
            enemy.moving = False
            if gap_to_player <= 99 and visible(enemy.position, run.position, collides):
                enemy.concealed = False
                enemy.reveal = .72
                notices.append("hidden_reveal")
            continue
        if enemy.reveal > 0:
            enemy.reveal = max(0., enemy.reveal - dt)
            continue
        enemy.cooldown = max(0, enemy.cooldown - dt)
        enemy.alerted = max(0, enemy.alerted - dt)
        if enemy.windup > 0:
            enemy.windup = max(0, enemy.windup-dt)
            if not enemy.windup:
                if enemy.throw_target:
                    launch_projectile(run, enemy)
                    enemy.throw_target = ()
                    enemy.cooldown = 3.2
                    continue
                target = actors.get(enemy.target)
                if target is not None and distance(enemy.position, target) < 45 and visible(enemy.position, target, collides):
                    if enemy.target == "player":
                        run.infection_until = run.elapsed + 1.35
                        return notices + ["infection_started"]
                    victim = run.actors[enemy.target]
                    if victim.status != "bitten":
                        victim.status, victim.infection = "bitten", INFECTION_SECONDS
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
            radius += sound_sight
        enemy.chasing = gap < radius and visible(enemy.position, target, collides)
        if enemy.chasing:
            enemy.target = target_id
            enemy.last_seen = target
            enemy.linger = 3.8 if enemy.kind == "stalker" else 2.8
        enemy.moving = False
        attack_range = 37
        if enemy.chasing and gap < attack_range and enemy.cooldown <= 0:
            enemy.target, enemy.windup = target_id, windup
            enemy.facing = facing(Vector2(target) - enemy.position)
            notices.append("warning")
        elif (enemy.kind == "thrower" and enemy.chasing and target_id == "player"
              and 95 < gap < 235 and enemy.cooldown <= 0):
            enemy.throw_target = tuple(target)
            enemy.windup = .76
            enemy.facing = facing(Vector2(target) - enemy.position)
            notices.append("throw_warning")
        elif enemy.chasing and enemy.cooldown <= 0:
            if enemy.kind == "stalker" and 83 < gap < 123 and run.elapsed % 3 < 2:
                continue
            burst = 1.33 if enemy.kind == "hunter" and 46 < gap < 122 else 1
            if outdoors and run.weather == "rain":
                speed *= .92
            follow(enemy, target, speed * burst * ENEMY_SPEED, dt, collides)
        elif not enemy.chasing and not enemy.cooldown:
            if enemy.linger > 0:
                enemy.linger = max(0, enemy.linger - dt)
                if enemy.last_seen and distance(enemy.position, enemy.last_seen) > 26:
                    follow(enemy, enemy.last_seen, speed * .65 * ENEMY_SPEED, dt, collides)
                continue
            if enemy.guard_door:
                follow(enemy, enemy.home, 35, dt, collides)
                continue
            phase = run.elapsed * .46 + enemy.home[0] * .063
            patrol = Vector2(enemy.home) + Vector2(math.cos(phase), math.sin(phase)) * 39
            follow(enemy, patrol, 29 * ENEMY_SPEED, dt, collides)
    return notices
