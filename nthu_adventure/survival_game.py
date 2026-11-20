"""Pygame entry point for Last Report."""
from __future__ import annotations

from dataclasses import asdict
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pygame
from pygame import Vector2

from .audio import AudioManager
from .constants import FPS, TILE, WINDOW_SIZE, WORLD_HEIGHT, WORLD_WIDTH
from .encounter_flow import EncounterFlow
from .expedition import MAIN_STEPS, MINUTE_SECONDS, SIGNAL_MINUTE, STOP_MINUTE, STORY_STEPS
from .interiors import create_rooms
from .localization import Localizer
from .paperworld import PaperWorld
from .survival import (
    CAMPUS_BUILDINGS, ENDING, FACING, GEAR, KINDS, OBSERVATIONS, STORY_ROOMS, STYLE_LIMITS,
    Actor, CampusSlots, RunStore, body, cross_door, distance, follow, nearby_targets,
    simulate, use_gear, visible,
)
from .ui import FontBook

SIZE = pygame.Rect((0, 0), WINDOW_SIZE)
NAME_BOX = pygame.Rect(570, 236, 422, 57)
NAME_LIMIT = 12
MAP_PAGE_SIZE = 8
LAMP_REACH = 310
NIGHT_VISION = 146
INK = (23, 33, 34)
PANEL = (30, 43, 43)
PAPER = (240, 235, 218)
MUTED = (174, 185, 169)
GOLD = (233, 184, 106)
RED = (230, 117, 94)
BLUE = (114, 181, 197)
INTRO_BEATS = (0, 8, 16, 25, 33, 40)
QUICK_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6)
PALETTE = ((219,157,111), (106,172,198), (190,139,86), (232,192,105), (150,169,151), (156,173,146))


def flashlight_shadows():
    """Create a black overlay with a soft pool and directional beam cut out."""
    reach = LAMP_REACH
    diameter = reach * 2 + 1
    east = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    east.fill((13, 26, 41, 210))
    for y in range(-151, 152):
        for x in range(-78, reach):
            falloff = math.hypot(x, y)
            pool = max(0, min(1, (78 - falloff) / 41))
            beam = min(1, (reach - falloff) / 92, (x + 8) / 38, (21 + x * .46 - abs(y)) / 25)
            strength = max(pool, beam)
            if strength > 0:
                east.set_at((x + reach, y + reach), (13, 26, 41, round(210 - 188 * strength)))
    return {
        "right": east,
        "up": pygame.transform.rotate(east, 90),
        "left": pygame.transform.rotate(east, 180),
        "down": pygame.transform.rotate(east, 270),
    }


class Game:
    def __init__(self, save_dir: Path | None = None):
        os.environ.setdefault("SDL_IME_SHOW_UI", "1")
        pygame.init()
        self.name_focused = False
        self.name_composition = ""
        self.store = RunStore(save_dir)
        self.profile = self.store.profile()
        self.resume_run = self.store.load()
        self.localizer = Localizer(self.profile.language)
        pygame.display.set_caption("清華拾光：別跟著聲音走")
        self.set_fullscreen(False if save_dir else self.profile.fullscreen)
        pygame.key.stop_text_input()
        self.canvas = pygame.Surface(WINDOW_SIZE)
        self.overlay = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
        self.lamp_shadows = None
        self.night_pool = None
        self.pending_scare = None
        self.scare_kind = None
        self.scare_time = 0.
        self.scare_ready = 0.
        self.clock = pygame.time.Clock()
        self.fonts = FontBook()
        self.audio = AudioManager()
        self.world = PaperWorld()
        self.rooms = create_rooms()
        self.slots = CampusSlots(self.world, self.rooms)
        if self.resume_run:
            self.slots.restore_supplies(self.resume_run)
            self.slots.restore_mutations(self.resume_run)
        self.encounters = EncounterFlow(self)
        self.world_map_bounds = pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT)
        self.building_entrances = {key: self.world.door(building) for key, building in CAMPUS_BUILDINGS.items()}
        self.map_points = {
            **self.slots.doors,
            "gate": self.slots.start,
            "lawn": self.slots.lawn,
            "lake": self.slots.lake,
            **self.building_entrances,
        }
        self.maps = {}
        self.map_page = 0
        self.event_page = 0
        self.map_selected = None
        self.scene = "title"
        self.previous = "title"
        self.active = True
        self.run_state = None
        self.buttons = []
        self.hotbar = []
        self.intro_time = 0
        self.end_time = 0
        self.moving = self.running = False
        self.toast = ""
        self.toast_until = self.autosave_at = self.bat_at = 0
        self.persistent_hint = ""
        self.card = ()
        self.card_values = {}
        self.card_speaker = self.card_quote = ""
        self.incident_time = 0
        self.outbreak_cue_until = 0
        self.pursuit_until = 0
        self.options = ()
        self.map_zoom = False
        self.debug_grid = False

    def tr(self, key, **values):
        return self.localizer.t("survival." + key, **values)

    def set_fullscreen(self, enabled):
        self.fullscreen = enabled
        self.screen = pygame.display.set_mode((0, 0) if enabled else WINDOW_SIZE, pygame.FULLSCREEN if enabled else pygame.RESIZABLE)
        if self.name_focused:
            pygame.key.start_text_input()
            self.position_name_input()

    def position_name_input(self):
        view = self.viewport()
        scale_x, scale_y = view.width / SIZE.width, view.height / SIZE.height
        pygame.key.set_text_input_rect(pygame.Rect(
            round(view.x + NAME_BOX.x * scale_x), round(view.y + NAME_BOX.y * scale_y),
            round(NAME_BOX.width * scale_x), round(NAME_BOX.height * scale_y),
        ))

    def focus_name(self, focused):
        self.name_focused = focused
        self.name_composition = ""
        if focused:
            pygame.key.start_text_input()
            self.position_name_input()
        else:
            pygame.key.stop_text_input()

    def append_name(self, text):
        printable = "".join(char for char in text if char.isprintable())
        self.profile.name = (self.profile.name + printable)[:NAME_LIMIT]

    def settings_save(self):
        self.profile.fullscreen = self.fullscreen
        self.store.write("profile", asdict(self.profile))

    def run(self):
        try:
            while self.active:
                dt = min(.05, self.clock.tick(FPS) / 1000)
                mouse = self.mouse()
                for event in pygame.event.get():
                    self.event(event, mouse)
                self.update(dt)
                self.update_audio(dt)
                self.draw(mouse)
                self.present()
        finally:
            if self.run_state:
                self.store.save(self.run_state)
            self.settings_save()
            self.audio.close()
            pygame.quit()

    def viewport(self):
        w, h = self.screen.get_size()
        scale = min(w / SIZE.width, h / SIZE.height)
        return pygame.Rect((w-SIZE.width*scale)/2, (h-SIZE.height*scale)/2, SIZE.width*scale, SIZE.height*scale)

    def mouse(self):
        view = self.viewport()
        x, y = pygame.mouse.get_pos()
        return ((x-view.x)*SIZE.width/view.width, (y-view.y)*SIZE.height/view.height)

    def present(self):
        self.screen.fill(INK)
        view = self.viewport()
        source = self.canvas if view.size == SIZE.size else pygame.transform.smoothscale(self.canvas, view.size)
        self.screen.blit(source, view)
        pygame.display.flip()

    def sound(self, key):
        if self.profile.sound:
            self.audio.play(key)

    def begin(self, seed=None):
        self.pending_scare = self.scare_kind = None
        self.scare_time = self.scare_ready = 0.
        self.run_state = self.slots.new(seed)
        self.resume_run = self.run_state
        self.scene = "intro"
        self.intro_time = 0
        self.end_time = 0
        self.autosave_at = self.bat_at = 0
        self.moving = self.running = False
        self.toast_until = 0
        self.incident_time = self.outbreak_cue_until = self.event_page = 0
        self.toast = ""
        self.persistent_hint = ""
        self.pursuit_until = 0
        self.store.save(self.run_state)
        self.focus_name(False)

    def resume(self):
        if self.resume_run is None:
            return
        self.run_state = self.resume_run
        self.pending_scare = self.scare_kind = None
        self.scare_time = self.scare_ready = 0.
        if self.run_state.area == "campus" and self.world.collides(body(self.run_state.position)):
            self.run_state.position = self.slots.near(self.run_state.position)
            self.run_state.trail.clear()
        self.scene = "intro" if self.run_state.intro else "play"
        self.intro_time = 0
        self.autosave_at = self.run_state.elapsed
        self.encounters.sync()

    def finish_intro(self):
        self.run_state.intro = False
        if self.intro_time >= 8:
            self.run_state.observe("storm")
        self.scene = "play"
        self.store.save(self.run_state)

    def notify(self, key, **values):
        message = self.tr(key, **values)
        if key == "route.outbreak":
            self.persistent_hint = message
            self.toast = ""
            self.toast_until = 0
            return
        self.toast = message
        self.toast_until = pygame.time.get_ticks() + 2800

    def event(self, event, mouse):
        if event.type == pygame.QUIT:
            self.active = False
        elif event.type == pygame.TEXTEDITING and self.name_focused:
            self.name_composition = event.text
        elif event.type == pygame.TEXTINPUT and self.name_focused:
            self.name_composition = ""
            self.append_name(event.text)
        elif event.type in (pygame.WINDOWSIZECHANGED, pygame.WINDOWFOCUSGAINED) and self.name_focused:
            self.position_name_input()
        elif event.type == pygame.MOUSEWHEEL and self.scene == "map":
            self.change_map_page(-event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.scene == "profile" and NAME_BOX.collidepoint(mouse):
                if not self.name_focused:
                    self.focus_name(True)
                return
            for rect, action, enabled in self.buttons:
                if enabled and rect.collidepoint(mouse):
                    self.action(action)
                    return
            if self.scene == "map":
                self.pick_map_marker(mouse)
            elif self.scene == "play":
                for i, rect in enumerate(self.hotbar):
                    if rect.collidepoint(mouse):
                        self.run_state.selected = i
                        self.sound("select")
                        return
        elif event.type == pygame.KEYDOWN:
            self.key(event.key, getattr(event, "mod", 0))

    def key(self, key, modifiers=0):
        scene = self.scene
        if key == pygame.K_F3:
            self.debug_grid = not self.debug_grid
            return
        if key == pygame.K_F11:
            self.set_fullscreen(not self.fullscreen)
            return
        if scene == "profile":
            self.profile_key(key, modifiers)
            return
        if scene == "intro" and key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.finish_intro()
        elif scene == "incident" and key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.finish_incident()
        elif scene == "play":
            if key in (pygame.K_e, pygame.K_RETURN):
                self.interact()
            elif key in QUICK_KEYS:
                self.run_state.selected = QUICK_KEYS.index(key)
            elif key == pygame.K_SPACE:
                self.use(self.run_state.selected)
            elif key == pygame.K_b:
                self.use(GEAR.index("bike"))
            elif key in (pygame.K_q, pygame.K_m, pygame.K_ESCAPE):
                if key == pygame.K_m and self.persistent_hint:
                    self.toast = ""
                    self.persistent_hint = ""
                    self.toast_until = 0
                self.scene = {pygame.K_q: "journal", pygame.K_m: "map", pygame.K_ESCAPE: "pause"}[key]
        elif scene == "card":
            if key in QUICK_KEYS and QUICK_KEYS.index(key) < len(self.options):
                self.resolve(self.options[QUICK_KEYS.index(key)])
            elif key == pygame.K_ESCAPE or (not self.options and key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE)):
                self.scene = "play"
        elif scene == "event_log" and key in (pygame.K_ESCAPE, pygame.K_q):
            self.scene = "journal"
        elif key == pygame.K_ESCAPE and scene in ("settings", "map", "journal", "pause", "confirm"):
            self.scene = self.previous if scene == "settings" else "title" if scene == "confirm" else "play"
        elif scene == "map" and key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.change_map_page(1 if key == pygame.K_PAGEDOWN else -1)
        elif (scene == "map" and key == pygame.K_m) or (scene == "journal" and key == pygame.K_q):
            self.scene = "play"
        elif scene == "death" and key == pygame.K_RETURN:
            self.begin()

    def profile_key(self, key, modifiers):
        if key == pygame.K_TAB and not self.name_composition:
            self.focus_name(not self.name_focused)
        elif not self.name_focused:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.action("start")
            elif key == pygame.K_ESCAPE:
                self.action("cancel_profile")
        elif not self.name_composition:
            if key == pygame.K_BACKSPACE:
                self.profile.name = self.profile.name[:-1]
            elif key == pygame.K_v and modifiers & pygame.KMOD_CTRL:
                try:
                    self.append_name(pygame.scrap.get_text() or "")
                except pygame.error:
                    pass
        # Enter and Escape at the field belong to the IME even after TEXTINPUT.

    def action(self, action):
        self.sound("select")
        if action == "customize":
            self.scene = "confirm" if self.resume_run else "profile"
            if self.scene == "profile":
                self.focus_name(True)
        elif action == "confirm":
            self.scene = "profile"
            self.focus_name(True)
        elif action == "cancel_profile":
            self.focus_name(False)
            self.scene = "title"
        elif action == "start":
            if self.name_composition:
                return
            self.settings_save()
            self.begin()
        elif action == "continue":
            self.resume()
        elif action == "skip":
            self.finish_intro()
        elif action == "skip_incident":
            self.finish_incident()
        elif action == "quit":
            self.active = False
        elif action == "title":
            if self.run_state:
                self.store.save(self.run_state)
                if self.run_state.death or self.run_state.ending:
                    self.resume_run = None
            self.run_state = None
            self.scene = "title"
        elif action == "again":
            self.begin()
        elif action == "settings":
            self.previous, self.scene = self.scene, "settings"
        elif action == "settings_back":
            self.settings_save()
            self.scene = self.previous
        elif action == "language":
            self.profile.language = "zh_TW" if self.profile.language == "en" else "en"
            self.localizer.set_language(self.profile.language)
        elif action == "screen":
            self.set_fullscreen(not self.fullscreen)
        elif action == "sound":
            self.profile.sound = not self.profile.sound
        elif action == "scares":
            self.profile.scares = not self.profile.scares
            self.pending_scare = self.scare_kind = None
            self.scare_time = 0.
        elif action.startswith("style/"):
            parts = action.split("/")
            part = parts[1]
            current = self.profile.appearance[part]
            value = int(parts[2]) if len(parts) == 3 else current + 1
            self.profile.appearance[part] = value % STYLE_LIMITS[part]
        elif action.startswith("choice/"):
            self.resolve(action.split("/",1)[1])
        elif action == "zoom":
            self.map_zoom = not self.map_zoom
            self.map_page = 0
        elif action in ("map_previous", "map_next"):
            self.change_map_page(1 if action == "map_next" else -1)
        elif action in ("event_previous", "event_next"):
            self.event_page += 1 if action == "event_next" else -1
        elif action == "event_log":
            self.event_page = 0
            self.scene = action
        elif action.startswith("map_pin/"):
            self.map_selected = action.split("/", 1)[1]
        elif action in ("play", "map", "journal"):
            self.scene = action

    def collides(self, rect):
        state = self.run_state
        return self.world.collides(rect) if state.area == "campus" else self.rooms[state.area].hit(rect)

    def update(self, dt):
        state = self.run_state
        if self.scene == "intro":
            self.intro_time += dt
            if self.intro_time >= INTRO_BEATS[-1]:
                self.finish_intro()
            return
        if self.scene == "incident":
            self.incident_time += dt
            if self.incident_time >= 5.5:
                self.finish_incident()
            return
        if self.scene == "ending":
            self.end_time += dt
            return
        if self.scene != "play":
            return
        self.scare_time = max(0., self.scare_time - dt)
        self.encounters.sync()
        keys = pygame.key.get_pressed()
        direction = Vector2(int(keys[pygame.K_d] or keys[pygame.K_RIGHT])-int(keys[pygame.K_a] or keys[pygame.K_LEFT]),
                            int(keys[pygame.K_s] or keys[pygame.K_DOWN])-int(keys[pygame.K_w] or keys[pygame.K_UP]))
        self.running = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        before = state.position
        for event in simulate(state, dt, direction, self.running, self.collides):
            if event.startswith("door_breach/"):
                self.notify("event.door_breach")
                self.cue_scare(event.split("/", 1)[1])
            elif event in ("warning", "call"):
                self.sound(event)
            elif event == "mimic_wait":
                if pygame.time.get_ticks() >= self.outbreak_cue_until:
                    self.notify("exp.mimic_nearby")
                    self.outbreak_cue_until = pygame.time.get_ticks() + 10000
            else:
                self.notify("event." + event)
        if self.pending_scare and self.profile.scares and state.elapsed >= self.scare_ready:
            self.scare_kind, self.pending_scare = self.pending_scare, None
            self.scare_time, self.scare_ready = .70, state.elapsed + 14.
            self.sound("scare")
        self.moving = distance(before, state.position) > .12
        if state.death:
            self.store.save(state)
            self.resume_run = None
            self.scene = "death"
        else:
            self.advance_crisis()
            if state.elapsed - self.autosave_at >= 18:
                self.store.save(state)
                self.autosave_at = state.elapsed

    def update_audio(self, dt):
        state = self.run_state
        if not self.profile.sound:
            self.audio.mix(None, False, dt)
            return
        cue = "dusk"
        if self.scene in ("ending", "death"):
            cue = "arrival"
        elif self.scene == "incident" or state and not state.intro and state.blackout:
            cue = "night"
            tick = pygame.time.get_ticks()
            if (self.scene == "play" and any(
                actor.infected and (actor.chasing or actor.windup) and distance(actor.position, state.position) < 255
                for _, actor in nearby_targets(state, state.area)
            )):
                self.pursuit_until = tick + 1800
            if tick < self.pursuit_until:
                cue = "pursuit"
        raining = self.scene in ("title", "profile", "confirm", "intro", "incident") or (
            state is not None and state.area == "campus" and state.weather == "rain"
        )
        self.audio.mix(cue, raining, dt)

    def advance_crisis(self):
        state = self.run_state
        if not state.blackout and state.minute >= STOP_MINUTE:
            state.blackout = True
            self.sound("power")
            self.notify("exp.blackout")
        if state.outbreak or not state.blackout:
            return
        point = self.slots.incidents[state.incident_site]
        close = state.area == "campus" and distance(state.position, point) < 150
        if close or state.minute >= SIGNAL_MINUTE:
            state.start_outbreak()
            if close:
                self.scene, self.incident_time = "incident", 0
            else:
                self.notify("route.outbreak")
            self.store.save(state)

    def finish_incident(self):
        self.scene = "play"
        self.notify("route.outbreak")

    def cue_scare(self, kind):
        if self.profile.scares and self.run_state.elapsed >= self.scare_ready:
            self.pending_scare = kind if kind in KINDS else "wanderer"

    def travel(self, area, source, destination, destination_clear, door):
        state = self.run_state
        origin = state.area
        group = cross_door(state, area, source, destination, self.collides, destination_clear, door)
        if area == "campus" and origin != area:
            for key in state.team:
                actor = state.actors[key]
                if actor.area == area and actor.status == "joined" and actor.choice == "escort":
                    actor.status = "gone"
                    event = self.encounters.encounter_for_actor(key)
                    event.outcome = "escort_complete"
                    state.add_gear("water")
                    self.notify("event.escort_complete")
        if group:
            self.notify("event.door_rattle")
            self.sound("warning")
        self.encounters.sync()

    def use(self, index):
        item = GEAR[index]
        tick = pygame.time.get_ticks()
        if item == "bat" and tick < self.bat_at:
            return
        feedback = use_gear(self.run_state, item, self.collides)
        if feedback == "used_bat":
            self.bat_at = tick + 450
            self.sound("bat")
        else:
            self.sound("select")
        self.notify("event." + feedback)

    def fixture_is_available(self, key):
        state = self.run_state
        if key in STORY_STEPS:
            goal_area = "campus" if state.goal_area in self.slots.outdoor_clues else state.goal_area
            return state.outbreak and state.area == goal_area and key == state.goal and not state.ending
        if key == "mimic":
            return state.outbreak
        if key == "side_exit":
            return state.area in state.shortcuts
        if key == "room_detail":
            return not any(self.encounters.targets())
        return True

    def interactions(self):
        run = self.run_state
        if run.area == "campus":
            for key, coord in self.slots.doors.items():
                yield "door", key, coord
            yield "fixture", "lawn", self.slots.lawn
            if run.goal_area in self.slots.outdoor_clues and self.fixture_is_available(run.goal):
                yield "fixture", run.goal, self.slots.outdoor_clues[run.goal_area]
        else:
            room = self.rooms[run.area]
            for fixture in room.fixtures:
                yield "fixture", fixture.key, fixture.point
            if self.fixture_is_available(run.goal):
                yield "fixture", run.goal, room.story_point
        yield from self.encounters.targets()
        for cache in run.caches:
            if cache.area == run.area and not cache.taken:
                yield "cache", cache.id, cache.position
        for key, npc in nearby_targets(run, run.area):
            if not run.outbreak or npc.status == "passing" or (key.startswith("enc_") and npc.status in ("waiting", "disguised")):
                continue
            if not npc.infected:
                yield "actor", key, npc.position
            elif npc.kind == "mimic" and not npc.chasing and not npc.windup:
                yield "fixture", "lure-"+key, npc.position

    def nearest(self):
        current = self.run_state.position
        return min(
            (candidate for candidate in self.interactions()
             if self.fixture_is_available(candidate[1])
             and distance(current, candidate[2]) <= (143 if candidate[1].startswith("lure-") else 63 if candidate[0] == "door" else 46)
             and visible(current, candidate[2], self.collides)),
            key=lambda candidate: distance(current, candidate[2]), default=None,
        )

    def label(self, kind, key):
        if kind == "door":
            return self.tr("location." + key) if key in STORY_ROOMS else self.campus_name(key)
        if kind == "encounter":
            return self.tr(self.encounters.title(self.run_state.encounters[key]))
        if kind == "actor":
            return self.actor_name(key)
        if key.startswith("lure-"):
            key = "mimic"
        if kind == "cache":
            cache = next(cache for cache in self.run_state.caches if cache.id == key)
            return self.tr("fixture.search_" + cache.container)
        return self.tr(f"{kind}.{key}")

    def show(self, title, text, options=(), *, speaker="", quote=None, **values):
        self.card = title, text
        self.card_values = values
        self.card_speaker = speaker
        self.card_quote = self.tr(quote) if quote else ""
        self.options = options
        self.scene = "card"

    def actor_name(self, key):
        event = self.encounters.encounter_for_actor(key) if key.startswith("enc_") else None
        return event.name(self.localizer.language) if event else self.tr("actor." + key)

    def interact(self):
        match = self.nearest()
        if not match:
            return
        kind, key, _ = match
        state = self.run_state
        if kind == "door":
            room = self.rooms[key]
            self.travel(key, self.slots.doors[key], room.entry, room.hit, key)
        elif kind == "encounter":
            self.encounters.open(key)
        elif kind == "cache":
            cache = next(cache for cache in state.caches if cache.id == key)
            cache.taken = True
            if cache.item:
                state.add_gear(cache.item)
                self.notify("event.found", item=self.tr("gear." + cache.item))
                self.sound("quest")
            else:
                self.notify("event.empty_container")
        elif kind == "actor":
            self.talk(key)
        elif key in ("exit", "side_exit"):
            outside = self.slots.side_exits[state.area] if key == "side_exit" else self.slots.doors[state.area]
            self.travel("campus", match[2], outside, self.world.collides,
                        state.area + "/side" if key == "side_exit" else state.area)
        else:
            self.read_fixture(key)
        self.store.save(state)

    def read_fixture(self, key):
        state = self.run_state
        if key in STORY_STEPS:
            self.read_story(key)
            return
        title = "fixture." + key
        text = "room_desc." + state.area if key == "room_detail" else "read." + key
        if key in ("lawn", "exhibit"):
            state.observe(key)
        if key.startswith("lure-"):
            line = state.heard_event or "plead.0"
            self.show("fixture.mimic", "read.mimic", ("test_voice", "leave"),
                      quote="exp.voice." + line)
            return
        self.show(title, text)

    def read_story(self, step):
        state = self.run_state
        if not self.fixture_is_available(step):
            return
        title = "fixture." + step
        if step == "sealed":
            self.show(title, "route.sealed.text", ("enter_refuge", "leave"))
        elif step == "echo_log" and (alternate := state.alternate_clue_site()):
            primary = state.route[tuple(state.route)[2]]
            backup = "story_backup_team" if state.team else "story_backup_alone"
            self.show(title, "route.echo_log.choice", ("story_primary", backup),
                      place=self.campus_name(primary), alternate=self.campus_name(alternate))
        elif step == "lock_log":
            self.show(title, "route.lock_log.text", ("story_leave_report", "story_search_report"),
                      place=self.campus_name(state.route["sealed"]))
        else:
            state.observe(step)
            self.show(title, "route." + step + ".text", place=self.campus_name(state.goal_area))

    def resolve_story(self, action):
        state = self.run_state
        if action in ("story_primary", "story_backup_team", "story_backup_alone"):
            if not self.fixture_is_available("echo_log") or not (alternate := state.alternate_clue_site()):
                return
            if action != "story_primary":
                state.route[tuple(state.route)[2]] = alternate
                if not state.team:
                    state.spend_time(MINUTE_SECONDS * 2)
            state.observe("echo_log")
            self.notify("route.marked", place=self.campus_name(state.goal_area))
        elif action in ("story_leave_report", "story_search_report") and self.fixture_is_available("lock_log"):
            state.observe("lock_log")
            if action == "story_search_report":
                state.spend_time(MINUTE_SECONDS * 2)
                state.add_gear("cell")
                self.notify("event.found", item=self.tr("gear.cell"))
            else:
                self.notify("route.marked", place=self.campus_name(state.goal_area))

    def route_hint(self):
        state = self.run_state
        if not state.outbreak:
            return self.tr("route.wait")
        return self.tr("route." + state.goal + ".goal", place=self.campus_name(state.goal_area))

    def talk(self, key):
        npc = self.run_state.actors[key]
        if key.startswith("enc_"):
            event = self.encounters.encounter_for_actor(key)
            options = ("separate/"+key, "leave") if npc.status == "bitten" else ("share/"+key, "leave")
            self.show("exp.companion", "read.bitten" if npc.status == "bitten" else "read.joined", options,
                      speaker=event.name(self.localizer.language),
                      quote="exp.voice.plead.1" if npc.status == "bitten" else "exp.voice.cooperate.1")
            return
        if npc.status == "bitten":
            self.show("actor."+key, "read.bitten", ("separate/"+key, "leave"))
            return
        if npc.status == "joined":
            options = ("share/"+key, "leave")
            self.show("actor."+key, "read.joined", options)
            return
        if key == "student":
            options = ("join/student", "student_search", "leave")
            if "exhibit" in self.run_state.observations:
                self.show("actor.student", "read.student_update", options)
                return
        elif key == "clerk":
            options = ("trade", "join/clerk", "leave")
        else:
            options = ("ask_stranger", "trust/stranger", "join/stranger", "leave")
        self.show("actor."+key, "read."+key, options)

    def resolve(self, action):
        state = self.run_state
        self.scene = "play"
        if action.startswith("event_"):
            verb, key = action.removeprefix("event_").split("/", 1)
            self.encounters.resolve(verb, key)
            self.store.save(state)
            return
        if action.startswith("story_"):
            self.resolve_story(action)
        elif "/" in action:
            verb, key = action.split("/", 1)
            npc = state.actors[key]
            if verb == "separate":
                npc.choice = "separate"
            elif verb == "share":
                if state.pack["water"]:
                    state.pack["water"] -= 1
                    npc.choice = "join"
                    npc.carried = False
                    self.notify("event.shared")
                else:
                    self.notify("event.no_water")
            elif len(state.team) >= 2:
                self.notify("event.team_full")
            elif verb == "trust" or key == "clerk":
                if not state.pack["water"]:
                    self.notify("event.no_water")
                else:
                    state.pack["water"] -= 1
                    npc.choice, npc.status = verb, "joined"
                    npc.carried = verb == "trust"
                    self.notify("event.joined")
            else:
                npc.choice, npc.status = verb, "joined"
                self.notify("event.joined")
        elif action == "student_search":
            self.show("actor.student", "read.student_search")
        elif action == "ask_stranger":
            self.show("actor.stranger", "read.ask_stranger")
        elif action == "trade":
            clerk = state.actors["clerk"]
            if clerk.choice == "traded":
                self.notify("event.traded_already")
            elif not state.pack["water"]:
                self.notify("event.no_water")
            else:
                state.pack["water"] -= 1
                state.add_gear("cell")
                clerk.choice = "traded"
                self.notify("event.traded")
        elif action == "test_voice":
            self.show("fixture.mimic", "read.test_voice")
        elif action == "enter_refuge" and self.fixture_is_available("sealed"):
            state.observe("sealed")
            state.ending = ENDING
            self.scene = "ending"
            self.end_time = 0
            self.resume_run = None
            self.sound("power")
        self.store.save(state)

    def words(self, text, point, size=18, color=PAPER, bold=False, anchor="topleft"):
        return self.fonts.draw(self.canvas, text, point, size, color, bold, anchor)

    def lines(self, text, point, size, width, color=PAPER):
        x, y = point
        for line in self.fonts.wrapped(text, size, width):
            self.words(line, (x, y), size, color)
            y += size + 8
        return y

    def panel(self, rect, color=PANEL, border=(78, 100, 94), radius=10):
        pygame.draw.rect(self.canvas, color, rect, border_radius=radius)
        pygame.draw.rect(self.canvas, border, rect, 1, border_radius=radius)

    def shade(self, color=(12, 19, 22, 192)):
        self.overlay.fill(color)
        self.canvas.blit(self.overlay, (0, 0))

    def button(self, rect, label, action, mouse, *, accent=False, enabled=True):
        rect = pygame.Rect(rect)
        hover = enabled and rect.collidepoint(mouse)
        fill = (208, 161, 95) if accent and hover else GOLD if accent else (53, 71, 68) if hover else PANEL
        self.panel(rect, fill, (158, 146, 114) if hover else (83, 105, 94))
        color = INK if accent else PAPER if enabled else (112, 130, 126)
        size = 19
        while size > 13 and self.fonts.get(size, accent).size(label)[0] > rect.width-18:
            size -= 1
        self.words(label, rect.center, size, color, accent, "center")
        self.buttons.append((rect, action, enabled))

    def button_key(self, rect, key, action, mouse, **flags):
        self.button(rect, self.tr("ui."+key), action, mouse, **flags)

    def paper_actor(self, point, direction="down"):
        return SimpleNamespace(player_x=point[0], player_y=point[1], facing=direction,
                               appearance=self.profile.appearance, running=self.running)

    def draw(self, mouse):
        self.buttons.clear()
        self.hotbar.clear()
        if self.scene == "intro":
            self.draw_intro(mouse)
        elif self.scene == "incident":
            self.draw_incident(mouse)
        elif self.scene in ("title", "profile", "confirm"):
            self.draw_menu(mouse)
        elif self.scene in ("play", "card", "pause", "map", "journal", "event_log", "death", "ending"):
            self.draw_play(mouse, hud=self.scene == "play")
            if self.scene == "pause":
                self.draw_pause(mouse)
            elif self.scene == "card":
                self.draw_card(mouse)
            elif self.scene == "map":
                self.draw_map(mouse)
            elif self.scene == "journal":
                self.draw_journal(mouse)
            elif self.scene == "event_log":
                self.draw_event_log(mouse)
            elif self.scene in ("death", "ending"):
                self.draw_final(mouse)
        elif self.scene == "settings":
            self.draw_settings(mouse)

    def draw_menu(self, mouse):
        point = self.slots.lake
        tick = pygame.time.get_ticks()
        camera = self.world.camera_for(point[0]+180, point[1]-38)
        self.world.draw_view(self.canvas, camera, (), self.paper_actor(point, "right"), False, tick)
        self.shade((19, 32, 46, 105))
        self.overlay.fill((0,0,0,0))
        for x in range(780):
            pygame.draw.line(self.overlay, (15, 25, 25, round(235*(1-x/780))), (x,0), (x,720))
        self.canvas.blit(self.overlay, (0, 0))
        self.draw_rain(tick, heavy=True)
        if self.scene == "title":
            self.words(self.tr("ui.brand"), (80, 110), 24, GOLD, True)
            self.words(self.tr("ui.title"), (77, 148), 57, PAPER, True)
            pygame.draw.line(self.canvas, (145, 131, 93), (82, 242), (408, 242), 2)
            for i, (label, action) in enumerate((("new", "customize"), ("continue", "continue"), ("settings", "settings"), ("quit", "quit"))):
                self.button_key((82, 280 + 62*i, 280, 50), label, action, mouse,
                                accent=i == 0, enabled=action != "continue" or self.resume_run is not None)
            self.words(self.tr("ui.unofficial"), (82, 650), 16, MUTED)
        elif self.scene == "confirm":
            self.shade()
            self.panel((332, 208, 616, 298))
            self.words(self.tr("ui.new"), (371, 244), 32, GOLD, True)
            self.lines(self.tr("ui.replace"), (374, 314), 21, 530)
            self.button_key((374, 425, 240, 48), "back", "cancel_profile", mouse)
            self.button_key((661, 425, 239, 48), "new", "confirm", mouse, accent=True)
        else:
            self.shade()
            self.panel((220, 88, 840, 545))
            self.words(self.tr("ui.profile"), (265, 126), 33, GOLD, True)
            portrait = self.world.characters.sprite("down", 0, self.profile.appearance, preview=True)
            pygame.draw.ellipse(self.canvas, (23, 34, 34), (366, 482, 76, 12))
            self.canvas.blit(portrait, portrait.get_rect(midbottom=(404, 487)))
            self.words(self.tr("ui.name"), (572, 201), 19, MUTED)
            self.draw_name_input(tick)
            for i, gender in enumerate(("male", "female")):
                self.button_key((570+i*211, 325, 200, 41), gender, f"style/gender/{i}", mouse,
                                accent=self.profile.appearance["gender"] == i)
            for i, part in enumerate(("shirt", "hair_style", "hair_color", "skin")):
                x, y = 570+i%2*211, 379+i//2*50
                style = self.profile.appearance[part]
                value = self.tr(f"hair.{style}") if part == "hair_style" else f"{style + 1}/{STYLE_LIMITS[part]}"
                label = f'{self.tr("ui."+part)}  {value}'
                self.button((x, y, 200, 41), label, "style/"+part, mouse)
            self.button_key((570, 497, 422, 56), "depart", "start", mouse, accent=True)
            self.button_key((570, 564, 422, 42), "back", "cancel_profile", mouse)

    def draw_name_input(self, tick):
        self.panel(NAME_BOX, INK, GOLD if self.name_focused else (78, 100, 94))
        saved_clip = self.canvas.get_clip()
        self.canvas.set_clip(NAME_BOX.inflate(-26, -8))
        name = self.words(self.profile.name, (NAME_BOX.x + 16, 250), 22)
        if self.name_composition:
            preedit = self.words(self.name_composition, name.topright, 22, GOLD)
            pygame.draw.line(self.canvas, GOLD, preedit.bottomleft, preedit.bottomright)
        elif self.name_focused and tick // 500 % 2:
            self.words("│", name.topright, 22)
        self.canvas.set_clip(saved_clip)
        self.words(self.tr("ui.name_input"), (NAME_BOX.x, 300), 14, MUTED)

    def draw_intro(self, mouse):
        beats = INTRO_BEATS
        i = next((i for i in range(5) if self.intro_time < beats[i+1]), 4)
        fraction = (self.intro_time-beats[i])/(beats[i+1]-beats[i])
        north = self.slots.start
        lake = self.slots.lake
        lawn = self.slots.lawn
        shots = (
            (north, (114, -12), (30,44)),
            (lake, (96, 24), (-65,-10)),
            (lake, (-56,13), (96,0)),
            (lawn, (18,35), (-50,-26)),
            (north, (45,20), (0, 0)),
        )
        pos, start, end = shots[i]
        drift = Vector2(start).lerp(end, fraction)
        tick = pygame.time.get_ticks()
        if i in (0, 1) and int(self.intro_time*13) % 3 == 0:
            drift.x += math.sin(self.intro_time*44)*3
        camera = self.world.camera_for(pos[0]+drift.x, pos[1]+drift.y)
        silhouette = (Actor("intro_student", Vector2(pos)+(-38,24)),) if i in (2,3) else ()
        self.world.draw_view(self.canvas, camera, (), self.paper_actor(Vector2(pos)+(38,57), "left"),
                             i==4, tick, survivors=silhouette)
        focus = Vector2(pos) - camera.topleft
        self.weather_fx("rain", i in (1, 2), focus, False, tick, intro=True)
        if i <= 1 and .43 < fraction < .50:
            self.shade((180, 207, 201, 106))
        if i in (1,2):
            self.overlay.fill((0,0,0,0))
            for j in range(10):
                x = int(focus.x - 510 + j*105 + fraction*140)
                y = int(focus.y - 44 + 26*math.sin(j))
                pygame.draw.ellipse(self.overlay,(143,171,168,38+j%3*10),(x,y,380,87))
            self.canvas.blit(self.overlay,(0,0))
        pygame.draw.rect(self.canvas, (17, 25, 27), (0, 0, 1280, 65))
        pygame.draw.rect(self.canvas, (17, 25, 27), (0, 535, 1280, 185))
        self.words(self.tr(f"intro.{i}.place"), (54, 22), 20, GOLD, True)
        self.lines(self.tr(f"intro.{i}.text"), (55, 581), 24, 1100)
        pygame.draw.line(self.canvas, GOLD, (0, 535), (1280*min(1,self.intro_time/40), 535), 2)
        self.button_key((1004, 654, 220, 43), "skip", "skip", mouse)

    def draw_incident(self, mouse):
        point = Vector2(self.slots.incidents[self.run_state.incident_site])
        camera = self.world.camera_for(*point)
        progress = min(1, self.incident_time / 5.5)
        victim = Actor("student", point.lerp(point + (61, 20), min(1, progress*1.5)), moving=progress<.65)
        attacker = Actor("mimic", (point + (-66, 15)).lerp(point + (42, 20), progress),
                         moving=progress < .88, windup=.7 if progress > .7 else 0)
        tick = pygame.time.get_ticks()
        self.world.draw_view(self.canvas, camera, (), self.paper_actor(self.run_state.position), False, tick,
                             enemies=(attacker,), survivors=(victim,))
        self.weather_fx("rain", True, point - camera.topleft, False, tick, intro=True)
        self.panel((41, 562, 1198, 126), INK)
        place = self.tr("route.place." + self.run_state.incident_site)
        self.words(self.run_state.clock + "  ·  " + place, (66, 580), 22, GOLD, True)
        self.lines(self.tr("exp.incident_text"), (67, 619), 19, 880)
        self.button_key((1018, 632, 190, 40), "skip", "skip_incident", mouse)

    def draw_coordinate_grid(self, camera):
        start_x = (camera.left // TILE) * TILE
        start_y = (camera.top // TILE) * TILE
        grid_color = (180, 190, 177, 105)
        grid = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
        for x in range(start_x, camera.right + TILE, TILE):
            pygame.draw.line(grid, grid_color, (x - camera.left, 0), (x - camera.left, WINDOW_SIZE[1]), 1)
            tile_x = x // TILE
            if tile_x % 5 == 0:
                self.words(str(tile_x), (x - camera.left + 2, 2), 12, (230, 120, 100), True)
        for y in range(start_y, camera.bottom + TILE, TILE):
            pygame.draw.line(grid, grid_color, (0, y - camera.top), (WINDOW_SIZE[0], y - camera.top), 1)
            tile_y = y // TILE
            if tile_y % 5 == 0:
                self.words(str(tile_y), (2, y - camera.top + 2), 12, (230, 120, 100), True)
        self.canvas.blit(grid, (0, 0))

    def draw_play(self, mouse, hud):
        state = self.run_state
        tick = pygame.time.get_ticks()
        outdoor = state.area == "campus"
        if outdoor:
            camera = self.world.camera_for(*state.position)
            offset = Vector2(camera.topleft)
            actors = [actor for _, actor in nearby_targets(state, state.area)]
            enemies = [actor for actor in actors if actor.infected]
            humans = [actor for actor in actors if not actor.infected]
            self.world.draw_view(self.canvas, camera, (), self.paper_actor(state.position, state.facing),
                                 self.moving, tick, state.riding, enemies, humans)
            for enemy in enemies:
                x, y = Vector2(enemy.position)-offset
                if SIZE.collidepoint(x,y):
                    self.enemy_mark(enemy, (x,y))
            self.weather_fx(state.weather, state.night, Vector2(state.position)-offset, state.lamp_on, tick, blackout=True)
            if self.debug_grid:
                self.draw_coordinate_grid(camera)
        else:
            offset = Vector2()
            room = self.rooms[state.area]
            self.canvas.blit(room.surface, (0, 0))
            for key, position in room.labels:
                self.words(self.tr(key), position, 15, (43, 54, 49), True, "center")
            actors = [actor for _, actor in nearby_targets(state, state.area)]
            layers = [(actor.position[1], actor) for actor in actors] + [(state.position[1],None)]
            for _, actor in sorted(layers, key=lambda layer: layer[0]):
                if actor is None:
                    self.world.characters.draw(self.canvas, state.position, state.facing, self.moving,
                                               self.profile.appearance, tick, .97, running=self.running)
                elif actor.infected:
                    self.world.characters.draw_zombie(self.canvas, actor.position, actor, tick)
                    self.enemy_mark(actor, actor.position)
                else:
                    variant = actor.identity + 17 if actor.identity >= 0 else sum(map(ord,actor.kind))
                    active = state.outbreak and actor.moving and actor.status in ("joined", "bitten")
                    appearance = {"shirt": variant % 6, "hair_color": variant % 5, "gender": variant % 2}
                    self.world.characters.draw(self.canvas, actor.position, actor.facing, active, appearance, tick, .95,
                                               stride=actor.stride)
                    if actor.status == "bitten":
                        pygame.draw.circle(self.canvas, RED, (round(actor.position[0]), round(actor.position[1])-58), 4)
        if not hud:
            return
        if outdoor:
            self.draw_building_names(camera)
        current = self.nearest()
        for kind, key, point in self.interactions():
            position = Vector2(point) - offset
            if not SIZE.inflate(-20, -125).collidepoint(position) or not self.fixture_is_available(key):
                continue
            if outdoor and not self.lit_at(point):
                continue
            if key in STORY_STEPS:
                x, y = round(position.x), round(position.y)
                pygame.draw.polygon(self.canvas, INK, ((x,y-11),(x+11,y),(x,y+11),(x-11,y)))
                pygame.draw.polygon(self.canvas, GOLD, ((x,y-10),(x+10,y),(x,y+10),(x-10,y)), 2)
            elif kind not in ("actor", "cache"):
                color = GOLD if current and current[1] == key else (218, 219, 190)
                pygame.draw.circle(self.canvas, color, position, 6, 2)
        if current:
            label = "E  ·  "+self.label(*current[:2])
            w = self.fonts.get(19, True).size(label)[0]+32
            self.panel((640-w//2, 575, w, 36), INK)
            self.words(label, (640, 593), 19, GOLD, True, "center")
        if pygame.time.get_ticks() < self.bat_at and (not outdoor or self.lit_at(state.position)):
            factor = 1-((self.bat_at-pygame.time.get_ticks())/450)
            direction = Vector2(FACING[state.facing]).rotate(-55+110*factor)
            start = Vector2(state.position)-offset+(0,-15)
            pygame.draw.line(self.canvas, GOLD, start+direction*22, start+direction*57, 5)
        if self.scare_time > 0 and self.profile.scares:
            self.draw_scare()
        self.draw_hud(mouse)

    def draw_scare(self):
        hold = min(1., self.scare_time / .42)
        self.overlay.fill((0, 0, 0, 0))
        alpha = round(105 * hold)
        pygame.draw.rect(self.overlay, (97, 33, 40, alpha), SIZE, round(50 - 21 * hold))
        pygame.draw.rect(self.overlay, (20, 18, 22, alpha // 2), SIZE, 12)
        self.canvas.blit(self.overlay, (0, 0))
        # A brief peripheral close-up leaves the player and doorway visible.
        sprite = self.world.characters.zombie_sprite(self.scare_kind, "down", 0, True)
        top = sprite.subsurface((0, 0, sprite.get_width(), max(12, sprite.get_height() // 2)))
        size = (round(top.get_width() * (4.1 - .7 * hold)), round(top.get_height() * (4.1 - .7 * hold)))
        portrait = pygame.transform.smoothscale(top, size)
        portrait.set_alpha(round(240 * hold))
        self.canvas.blit(portrait, portrait.get_rect(midleft=(2, 354)))

    def campus_name(self, key):
        building = CAMPUS_BUILDINGS.get(key)
        return self.localizer.t(building["label"]) if building else self.tr("location." + key)

    def draw_building_names(self, camera):
        region = pygame.Rect(18, 126, 1244, 440)
        player = Vector2(self.run_state.position) - camera.topleft
        occupied = [pygame.Rect(round(player.x)-25, round(player.y)-63, 50, 77)]
        candidates = [
            (key, point) for key, point in self.building_entrances.items()
            if camera.collidepoint(point) and self.lit_at(point)
        ]
        for key, entrance in sorted(candidates, key=lambda item: distance(item[1], self.run_state.position)):
            name = self.campus_name(key)
            width = self.fonts.get(16, True).size(name)[0] + 20
            anchor = entrance - camera.topleft
            label = pygame.Rect(0, 0, width, 25)
            for offset in (24, -24, 51, -51):
                label.center = (round(anchor.x), round(anchor.y + offset))
                label.clamp_ip(region)
                if label.inflate(8, 6).collidelist(occupied) == -1:
                    self.panel(label, INK, (104, 123, 107), radius=6)
                    self.words(name, label.center, 16, PAPER, True, "center")
                    occupied.append(label)
                    break

    def enemy_mark(self, enemy, point):
        x, y = map(round, point)
        color = KINDS.get(enemy.kind, KINDS["wanderer"])[-1]
        height = {"crawler": 51, "brute": 96, "caller": 84}.get(enemy.kind, 74)
        if enemy.windup:
            pygame.draw.arc(self.canvas, RED, (x-24, y-15, 48, 27), 0, math.tau, 4)
            self.words("!", (x, y-height-13), 19, RED, True, "center")
        elif enemy.chasing and distance(enemy.position, self.run_state.position) <= 182:
            self.words(self.tr("infected." + (enemy.kind if enemy.kind in KINDS else "wanderer")),
                       (x, y-height), 13, color, True, "midbottom")

    def lamp_shadow(self):
        if self.lamp_shadows is None:
            self.lamp_shadows = flashlight_shadows()
        return self.lamp_shadows[self.run_state.facing]

    def lit_at(self, point):
        state = self.run_state
        if not state.night or distance(point, state.position) <= NIGHT_VISION:
            return True
        if not state.lamp_on:
            return False
        x, y = (Vector2(point) - state.position) + (LAMP_REACH, LAMP_REACH)
        shadow = self.lamp_shadow()
        pixel = (round(x), round(y))
        return shadow.get_rect().collidepoint(pixel) and shadow.get_at(pixel).a < 167

    def draw_rain(self, tick, *, heavy=False):
        self.overlay.fill((0, 0, 0, 0))
        for i in range(180 if heavy else 86):
            layer = i % 3
            x = (i * 377 - int(tick * (.10 + layer * .07))) % 1324
            y = (i * 137 + int(tick * (.38 + layer * .20))) % 756 - 22
            length = 8 + layer * 9
            pygame.draw.aaline(self.overlay, (171, 205, 216, 92 + layer * 47),
                               (x, y), (x - length * .35, y + length))
        self.canvas.blit(self.overlay, (0, 0))

    def ambient_night(self):
        if self.night_pool is None:
            size = 226
            color = (13, 26, 41)
            self.night_pool = pygame.Surface((size*2+1, size*2+1), pygame.SRCALPHA)
            self.night_pool.fill((*color, 210))
            for radius in range(size, 70, -1):
                blend = (radius - 71) / (size - 71)
                amount = 78 + round(132 * blend * blend * (3 - 2*blend))
                pygame.draw.circle(self.night_pool, (*color, amount), (size, size), radius)
        return self.night_pool

    def weather_fx(self, weather, night, focus, lamp, tick, intro=False, *, blackout=False):
        if night and blackout:
            self.overlay.fill((13, 26, 41, 210))
            pool = self.ambient_night()
            self.overlay.blit(pool, pool.get_rect(center=focus), special_flags=pygame.BLEND_RGBA_MIN)
            if lamp:
                shadow = self.lamp_shadow()
                self.overlay.blit(shadow, shadow.get_rect(center=focus), special_flags=pygame.BLEND_RGBA_MIN)
            self.canvas.blit(self.overlay, (0, 0))
        elif night or weather in ("rain", "cloud"):
            self.shade((16, 29, 44, 119 if night else 37 if weather == "rain" else 21))
        if weather == "rain":
            self.draw_rain(tick, heavy=intro)

    def draw_hud(self, mouse):
        state = self.run_state
        self.panel((23, 21, 263, 97), INK)
        if state.area in STORY_ROOMS:
            place = self.tr("location." + state.area)
        elif state.area != "campus":
            place = self.campus_name(state.area)
        else:
            place = self.tr("weather." + state.weather)
        self.words(state.clock, (267, 34), 16, GOLD, True, "topright")
        self.words(place, (39, 34), 15 if self.fonts.get(17, True).size(place)[0] > 173 else 17, PAPER, True)
        for y, key, value, color in ((65,"hunger",state.hunger,GOLD),(90,"thirst",state.thirst,BLUE)):
            self.words(self.tr("ui."+key), (39, y-4), 14, MUTED)
            pygame.draw.rect(self.canvas,(59,72,70),(118,y,116,8),border_radius=4)
            pygame.draw.rect(self.canvas, RED if value < 23 else color,(118,y,116*value/100,8),border_radius=4)
            self.words(f"{math.ceil(value):d}", (268, y+4), 12, PAPER, False, "midright")
        self.button_key((1033, 23, 109, 37), "map", "map", mouse)
        self.button_key((1149, 23, 108, 37), "journal", "journal", mouse)
        if state.team:
            self.panel((1008, 72, 249, 27+25*len(state.team)), INK)
            self.words(self.tr("ui.team"), (1024, 79), 13, MUTED)
            for i, key in enumerate(state.team):
                actor = state.actors[key]
                label = self.actor_name(key)
                if actor.status == "bitten":
                    label += f"  ·  {self.tr('ui.infected')} {math.ceil(actor.infection)}"
                self.words(label, (1025, 101+25*i), 15, RED if actor.status=="bitten" else PAPER)
        if self.persistent_hint:
            self.panel((368, 20, 544, 38), INK)
            self.words(self.persistent_hint, (640, 39), 17, PAPER, False, "center")
        if self.toast and pygame.time.get_ticks() < self.toast_until:
            top = 63 if self.persistent_hint else 20
            self.panel((368, top, 544, 38), INK)
            self.words(self.toast, (640, top + 19), 17, PAPER, False, "center")
        self.panel((310, 622, 660, 94), INK)
        for i, item in enumerate(GEAR):
            rect = pygame.Rect(318+107*i, 631, 101, 57)
            self.hotbar.append(rect)
            select = i == state.selected
            self.panel(rect, (63,67,51) if select else (47,58,56) if rect.collidepoint(mouse) else (34,47,46),
                       GOLD if select else (91,108,98))
            color = PALETTE[i] if state.pack[item] else (115,128,122)
            self.gear_icon(item, (rect.centerx, rect.y+24), color)
            self.words(str(i+1), (rect.x+7, rect.y+5), 12, MUTED)
            self.words(self.tr("gear."+item), (rect.centerx,rect.bottom-5), 12, PAPER, False, "midbottom")
            amount = f"{round(state.battery)}%" if item=="lamp" and state.pack[item] else str(state.pack[item])
            self.words(amount, (rect.right-7,rect.y+9), 12, color, True, "midright")
        self.words(self.tr("gear_tip." + GEAR[state.selected]), (640, 704), 15, PAPER, False, "center")
        self.words(self.tr("ui.controls"), (1259, 687), 13, MUTED, False, "bottomright")
        if state.area == "campus" and state.night:
            self.words(self.tr("weather.night"), (39, 128), 15, PAPER, True)
            if not state.lamp_on:
                hint = "ui.night_lamp" if state.pack["lamp"] and state.battery > 0 else "ui.night_map"
                self.words(self.tr(hint), (39, 153), 14, MUTED)

    def gear_icon(self, item, center, color):
        x,y = center
        if item == "water":
            pygame.draw.rect(self.canvas,color,(x-6,y-8,12,19),border_radius=4)
            pygame.draw.rect(self.canvas,color,(x-3,y-12,6,5),border_radius=2)
            pygame.draw.line(self.canvas,INK,(x-3,y+2),(x+3,y+2),2)
        elif item == "bat":
            pygame.draw.line(self.canvas,color,(x-8,y+8),(x+4,y-3),4)
            pygame.draw.line(self.canvas,color,(x-1,y+1),(x+8,y-7),8)
        elif item == "bike":
            for move_x in (-10,10):
                pygame.draw.circle(self.canvas,color,(x+move_x,y+4),6,2)
            pygame.draw.lines(self.canvas,color,True,[(x-10,y+4),(x-4,y-5),(x+3,y+4),(x+10,y+4),(x+6,y-7)],2)
        elif item == "lamp":
            pygame.draw.polygon(self.canvas,color,[(x-11,y-7),(x-5,y-7),(x-2,y-4),(x+11,y-4),(x+11,y+4),(x-2,y+4),(x-5,y+7),(x-11,y+7)])
        elif item == "cell":
            pygame.draw.rect(self.canvas,color,(x-6,y-8,12,17),2,border_radius=3)
            pygame.draw.line(self.canvas,color,(x-2,y-10),(x+2,y-10),2)
            pygame.draw.line(self.canvas,color,(x,y-4),(x,y+3),2)
            pygame.draw.line(self.canvas,color,(x-3,y),(x+3,y),2)
        else:
            pygame.draw.ellipse(self.canvas,color,(x-12,y-7,24,15))
            pygame.draw.line(self.canvas,INK,(x-7,y+2),(x+7,y+2),2)

    def draw_pause(self, mouse):
        self.shade()
        self.panel((464, 146, 352, 427))
        self.words(self.tr("ui.pause"), (640, 191), 32, GOLD, True,"center")
        for i,(label,action) in enumerate((("back","play"),("settings","settings"),("save_title","title"),("quit","quit"))):
            self.button_key((500,244+i*67,280,52),label,action,mouse,accent=i==0)

    def draw_settings(self, mouse):
        self.canvas.fill(INK)
        self.panel((402, 146, 476, 427))
        self.words(self.tr("ui.settings"),(640,194),34,GOLD,True,"center")
        self.button((455,244,370,53),"中文 / English","language",mouse)
        self.button_key((455,313,370,53),"window" if self.fullscreen else "fullscreen","screen",mouse)
        self.button_key((455,382,370,53),"sound_off" if self.profile.sound else "sound_on","sound",mouse)
        self.button_key((455,445,370,51), "scares_off" if self.profile.scares else "scares_on", "scares", mouse)
        self.button_key((455,521,370,53),"back","settings_back",mouse,accent=True)

    def draw_card(self, mouse):
        self.shade((14, 23, 25, 127))
        self.panel((232, 229, 816, 425), INK)
        title, text = self.card
        headline = self.tr(title)
        title_size = 29 if self.fonts.get(29, True).size(headline)[0] <= 720 else 23
        self.words(headline, (273,260), title_size, GOLD, True)
        content = self.tr(text, **self.card_values)
        text_size = 20 if len(self.fonts.wrapped(content, 20, 720)) <= 4 else 17
        y = self.lines(content, (274,317), text_size, 720)
        if self.card_speaker:
            quote = (self.card_speaker + "  ·  " + self.card_quote) if self.card_quote else self.card_speaker
            self.lines(quote, (274, min(y + 12, 414)), 17, 720, MUTED)
        elif self.card_quote:
            self.lines(self.card_quote, (274, min(y + 12, 414)), 17, 720, MUTED)
        for i, action in enumerate(self.options):
            key = action.split("/")[0]
            self.button((274+i%2*365, 470+i//2*56, 347, 45),
                        f"{i+1}  ·  "+self.tr("choice."+key), "choice/"+action, mouse)
        self.button_key((782, 597, 222, 38), "close","play", mouse, accent=not self.options)

    def draw_journal(self, mouse):
        self.shade()
        self.panel((213, 76, 854, 567))
        self.words(self.tr("ui.journal_title"), (253, 104), 33, GOLD, True)
        state = self.run_state
        keys = [key for key in state.observations if key in OBSERVATIONS]
        y = 165
        for key in keys[-4:]:
            self.words(self.tr("clue."+key+".title"), (255, y), 17, GOLD, True)
            y = self.lines(self.tr("clue."+key+".text"), (256,y+22), 17, 763, MUTED)+10
        if not keys:
            y = self.lines(self.tr("ui.empty_journal"), (257,y), 20, 759, MUTED)+12
        if state.outbreak:
            stop = tuple(state.route).index(state.goal) + 1
            self.words(self.tr("route.progress", stop=stop, total=len(state.route)), (257, 483), 15, MUTED, True)
            y = 499
        self.lines(self.route_hint(), (257, min(511,y+12)), 19, 760, GOLD)
        self.button_key((255, 573, 225, 39), "event_log", "event_log", mouse)
        self.button_key((807, 573, 217, 39), "back","play",mouse,accent=True)

    def draw_event_log(self, mouse):
        self.shade()
        self.panel((213, 76, 854, 567))
        self.words(self.tr("ui.event_log"), (253, 104), 33, GOLD, True)
        encounters = self.run_state.encounters.values()
        history = sorted((event for event in encounters if event.clock), key=lambda event: event.clock, reverse=True) if self.run_state.outbreak else []
        page_count = max(1, math.ceil(len(history) / 5))
        self.event_page = max(0, min(self.event_page, page_count - 1))
        if not history:
            self.lines(self.tr("exp.log_empty"), (254, 182), 20, 760, MUTED)
        for i, event in enumerate(history[self.event_page*5:self.event_page*5+5]):
            y = 174 + i*76
            h, m = divmod(event.clock % 1440, 60)
            self.words(f"{h:02d}:{m:02d}", (254,y), 17, MUTED)
            name = self.tr(self.encounters.title(event)) + "  ·  " + event.name(self.localizer.language)
            self.words(name, (323,y), 19, GOLD, True)
            desc = self.encounters.result_key(event) if event.outcome else "exp.log_" + event.status
            self.lines(self.tr(desc), (323,y+27), 15, 690)
        self.button_key((254, 574, 120, 38), "map_previous", "event_previous", mouse, enabled=self.event_page > 0)
        self.words(f"{self.event_page+1} / {page_count}", (418, 594), 15, MUTED, False, "center")
        self.button_key((463, 574, 120, 38), "map_next", "event_next", mouse, enabled=self.event_page+1 < page_count)
        self.button_key((808, 574, 215, 38), "back", "journal", mouse, accent=True)

    def map_layer(self):
        if self.map_zoom:
            bounds = pygame.Rect(75*32,37*32,76*32,91*32)
        else:
            bounds = self.world_map_bounds
        scale = min(800/bounds.width, 500/bounds.height)
        w,h = round(bounds.width*scale), round(bounds.height*scale)
        rect = pygame.Rect(470-w//2, 121, w, h)
        if self.map_zoom not in self.maps:
            layer = pygame.transform.smoothscale(self.world.ground.subsurface(bounds), (w,h))
            self.maps[self.map_zoom] = layer
        return self.maps[self.map_zoom], bounds, rect, scale

    def map_pin_positions(self, bounds, rect, scale):
        return {
            key: (Vector2(point) - bounds.topleft) * scale + rect.topleft
            for key, point in self.map_points.items()
            if bounds.collidepoint(point)
        }

    @staticmethod
    def map_pin_at(mouse, pins):
        nearest = min(pins, key=lambda key: pins[key].distance_squared_to(mouse), default=None)
        return nearest if nearest is not None and pins[nearest].distance_squared_to(mouse) <= 9**2 else None

    def change_map_page(self, delta):
        _, bounds, _, _ = self.map_layer()
        count = sum(bounds.collidepoint(point) for point in self.map_points.values())
        last_page = max(0, (count - 1) // MAP_PAGE_SIZE)
        self.map_page = max(0, min(self.map_page + delta, last_page))

    def pick_map_marker(self, mouse):
        _, bounds, rect, scale = self.map_layer()
        pins = self.map_pin_positions(bounds, rect, scale)
        key = self.map_pin_at(mouse, pins)
        if key is not None:
            self.map_selected = key
            self.map_page = list(pins).index(key) // MAP_PAGE_SIZE

    def draw_map(self, mouse):
        self.shade()
        self.panel((128, 58, 1024, 619))
        self.words(self.tr("ui.map_title"), (166, 77), 29, GOLD, True)
        image, bounds, map_rect, scale = self.map_layer()
        self.canvas.blit(image, map_rect)
        state = self.run_state
        pins = self.map_pin_positions(bounds, map_rect, scale)
        page_count = max(1, math.ceil(len(pins) / MAP_PAGE_SIZE))
        start = self.map_page * MAP_PAGE_SIZE
        page = list(pins)[start:start + MAP_PAGE_SIZE]
        rows = {key: pygame.Rect(778, 144 + 34*i, 316, 30) for i, key in enumerate(page)}
        hovered_row = next((key for key, row in rows.items() if row.collidepoint(mouse)), None)
        highlighted = hovered_row or self.map_pin_at(mouse, pins) or self.map_selected
        for key, pin in pins.items():
            pygame.draw.circle(self.canvas, INK, pin, 5)
            pygame.draw.circle(self.canvas, GOLD if key in rows else MUTED, pin, 3)
        if state.outbreak and not state.ending:
            target = pins.get(state.goal_area)
            if state.goal_area in self.slots.outdoor_clues:
                outdoor_point = self.slots.outdoor_clues[state.goal_area]
                if bounds.collidepoint(outdoor_point):
                    target = (Vector2(outdoor_point) - bounds.topleft) * scale + map_rect.topleft
            if target is not None:
                x, y = target
                pygame.draw.polygon(self.canvas, GOLD, ((x,y-11),(x+11,y),(x,y+11),(x-11,y)), 2)
        point = state.position if state.area == "campus" else self.slots.doors[state.area]
        if bounds.collidepoint(point):
            pin = (Vector2(point) - bounds.topleft) * scale + map_rect.topleft
            pygame.draw.circle(self.canvas, PAPER, pin, 7, 2)
        if highlighted in pins:
            pin = pins[highlighted]
            pygame.draw.circle(self.canvas, INK, pin, 9, 4)
            pygame.draw.circle(self.canvas, GOLD, pin, 8, 2)
            name = self.campus_name(highlighted)
            width = self.fonts.get(16, True).size(name)[0] + 22
            tag = pygame.Rect(0, 0, width, 27)
            tag.midbottom = (round(pin.x), round(pin.y)-12)
            tag.clamp_ip(pygame.Rect(149, 121, 609, 500))
            self.panel(tag, INK, GOLD, radius=6)
            self.words(name, tag.center, 16, PAPER, True, "center")
        self.words(self.tr("ui.landmarks"), (779, 107), 20, GOLD, True)
        for key, row in rows.items():
            self.button(row, self.campus_name(key), "map_pin/" + key, mouse, accent=key == highlighted)
        self.button_key((778, 426, 102, 32), "map_previous", "map_previous", mouse, enabled=self.map_page > 0)
        self.words(f"{self.map_page + 1} / {page_count}", (936, 442), 15, MUTED, False, "center")
        self.button_key((992, 426, 102, 32), "map_next", "map_next", mouse, enabled=self.map_page + 1 < page_count)
        if state.outbreak:
            self.lines(self.route_hint(), (779, 474), 16, 316, GOLD)
        self.button_key((778, 543, 316, 42), "full_map" if self.map_zoom else "route_map", "zoom", mouse)
        self.button_key((778, 595, 316, 42), "back", "play", mouse, accent=True)

    def draw_final(self, mouse):
        state = self.run_state
        if state.ending and self.end_time < 5.5:
            tint = min(247, round(75 + self.end_time * 32))
            self.shade((16, 13, 19, tint))
            x, y = self.rooms[state.area].entry
            door = pygame.Rect(x-32, y-34, 65, 50)
            pygame.draw.rect(self.canvas, (56, 50, 51), door, border_radius=3)
            for line in range(door.x+7, door.right, 8):
                pygame.draw.line(self.canvas, (91, 77, 80), (line,door.top+3), (line,door.bottom-3), 2)
            self.panel((285, 626, 710, 57), INK)
            hint = "ending.echo" if self.end_time >= 2.8 else "ending.arrival"
            self.words(self.tr(hint), (640,655), 19, GOLD, True, "center")
            return
        self.shade()
        self.panel((282, 143, 716, 449))
        if state.ending:
            title, description = "ending.title", "ending.text"
        else:
            title, description = "death.title", "death."+state.death
        self.words(self.tr(title), (327,181), 32 if state.ending else 40, RED, True)
        name = self.profile.name or self.tr("ui.default_name")
        y = self.lines(self.tr(description, name=name), (329,260), 21, 615)
        if state.ending:
            if state.team:
                person = self.actor_name(state.team[0])
                self.lines(self.tr("ending.with_team", person=person), (331,y+14), 17, 615, MUTED)
            else:
                self.lines(self.tr("ending.solo"), (331,y+14), 17, 615, MUTED)
        else:
            self.lines(self.tr("death.reset"), (331,y+18), 18, 615, MUTED)
        self.button_key((330, 510, 277, 48), "title_menu","title",mouse)
        self.button_key((668, 510, 277, 48), "again","again",mouse,accent=True)
