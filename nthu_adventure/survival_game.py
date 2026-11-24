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
from .content import WATERS
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
from .survival_ui import (
    BLUE, DIRECTORY, FIELD_MAP, GOLD, INK, LINE, MUTED, PANEL, PAPER, RED, TRACK,
    InterfaceArt, campus_atlas, cut_panel, icon,
)

SIZE = pygame.Rect((0, 0), WINDOW_SIZE)
NAME_BOX = pygame.Rect(570, 236, 422, 57)
NAME_LIMIT = 12
MAP_PAGE_SIZE = 8
MAP_SHEET = pygame.Rect(36, 91, 838, 564)
MAP_FOCUS = pygame.Rect(26*TILE, 19*TILE, 130*TILE, 126*TILE)
SIGHTING_SECONDS = 50
NIGHT_VISION = 146
INTRO_BEATS = (0, 8, 16, 25, 33, 40)
QUICK_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6)
PALETTE = ((219,157,111), (106,172,198), (190,139,86), (232,192,105), (150,169,151), (156,173,146))


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
        self.night_pool = None
        self.pending_scare = None
        self.scare_kind = None
        self.scare_time = 0.
        self.scare_ready = 0.
        self.clock = pygame.time.Clock()
        self.fonts = FontBook()
        self.interface = InterfaceArt()
        self.audio = AudioManager()
        self.world = PaperWorld()
        self.rooms = create_rooms()
        self.slots = CampusSlots(self.world, self.rooms)
        if self.resume_run:
            self.slots.restore_supplies(self.resume_run)
            self.slots.restore_mutations(self.resume_run)
            self.slots.restore_access(self.resume_run)
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
        self.map_return = "play"
        self.map_sightings = {}
        self.sighting_check = 0.
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
        self.card_event = False
        self.incident_time = 0
        self.outbreak_cue_until = 0
        self.pursuit_until = 0
        self.options = ()
        self.map_zoom = True
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
        self.reset_surveys()
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
        self.reset_surveys()
        self.encounters.sync()

    def reset_surveys(self):
        self.map_page = 0
        self.map_selected = None
        self.map_return = "play"
        self.map_sightings.clear()
        self.sighting_check = 0.

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
            elif key in QUICK_KEYS[:len(GEAR)]:
                self.run_state.selected = QUICK_KEYS.index(key)
            elif key == pygame.K_SPACE:
                self.use(self.run_state.selected)
            elif key == pygame.K_b:
                self.use(GEAR.index("bike"))
            elif key == pygame.K_g and not self.run_state.infection_until:
                if self.encounters.drop_parcel():
                    self.store.save(self.run_state)
            elif key in (pygame.K_q, pygame.K_m, pygame.K_ESCAPE):
                if key == pygame.K_m and self.persistent_hint:
                    self.toast = ""
                    self.persistent_hint = ""
                    self.toast_until = 0
                if key == pygame.K_m:
                    self.open_map()
                else:
                    self.scene = "journal" if key == pygame.K_q else "pause"
        elif scene == "card":
            if key in QUICK_KEYS and QUICK_KEYS.index(key) < len(self.options):
                self.resolve(self.options[QUICK_KEYS.index(key)])
            elif key == pygame.K_m and self.card_event and not self.options:
                self.open_map("card")
            elif key == pygame.K_ESCAPE or (not self.options and key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE)):
                self.scene = "play"
        elif scene == "event_log" and key in (pygame.K_ESCAPE, pygame.K_q):
            self.scene = "journal"
        elif scene == "map" and key in (pygame.K_ESCAPE, pygame.K_m):
            self.scene = self.map_return
        elif key == pygame.K_ESCAPE and scene in ("settings", "journal", "pause", "confirm"):
            self.scene = self.previous if scene == "settings" else "title" if scene == "confirm" else "play"
        elif scene == "map" and key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.change_map_page(1 if key == pygame.K_PAGEDOWN else -1)
        elif scene == "journal" and key == pygame.K_q:
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
        elif action == "map":
            self.open_map()
        elif action == "event_map":
            self.open_map("card")
        elif action == "map_back":
            self.scene = self.map_return
        elif action in ("map_previous", "map_next"):
            self.change_map_page(1 if action == "map_next" else -1)
        elif action in ("event_previous", "event_next"):
            self.event_page += 1 if action == "event_next" else -1
        elif action == "event_log":
            self.event_page = 0
            self.scene = action
        elif action.startswith("map_pin/"):
            self.map_selected = action.split("/", 1)[1]
        elif action in ("play", "journal"):
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
            else:
                self.notify("event." + event)
        if not state.infection_until and self.encounters.advance():
            self.store.save(state)
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
            self.record_sightings()
            if state.elapsed - self.autosave_at >= 18:
                self.store.save(state)
                self.autosave_at = state.elapsed

    def record_sightings(self):
        state = self.run_state
        if not state.outbreak or state.area != "campus" or state.elapsed < self.sighting_check:
            return
        self.sighting_check = state.elapsed + .45
        self.map_sightings = {key: (point, time) for key, (point, time) in self.map_sightings.items()
                              if state.elapsed - time <= SIGHTING_SECONDS}
        sight_range = NIGHT_VISION if state.night else 360
        for key, actor in nearby_targets(state, "campus"):
            if (actor.infected and not actor.concealed and
                    distance(actor.position, state.position) <= sight_range and
                    visible(state.position, actor.position, self.world.collides)):
                self.map_sightings[key] = tuple(actor.position), state.elapsed

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
                    if event:
                        event.outcome = "escort_complete"
        if group:
            self.notify("event.door_rattle")
            self.sound("warning")
        self.encounters.sync()

    def use(self, index):
        if self.run_state.infection_until:
            return
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
        self.notify("event.empty_bat" if item == "bat" and feedback == "empty" else "event." + feedback)

    def fixture_is_available(self, key):
        state = self.run_state
        if key in STORY_STEPS:
            goal_area = "campus" if state.goal_area in self.slots.outdoor_clues else state.goal_area
            return state.outbreak and state.area == goal_area and key == state.goal and not state.ending
        if key == "mimic":
            return state.outbreak
        if key == "room_detail":
            return not any(self.encounters.targets())
        return True

    def interactions(self):
        run = self.run_state
        if run.area == "campus":
            for key, coord in self.slots.doors.items():
                yield "door", key, coord
            for key, coord in self.slots.side_exits.items():
                yield "door", key + "/side", coord
            yield "fixture", "lawn", self.slots.lawn
            if run.goal_area in self.slots.outdoor_clues and self.fixture_is_available(run.goal):
                yield "fixture", run.goal, self.slots.outdoor_clues[run.goal_area]
        else:
            room = self.rooms[run.area]
            for fixture in room.fixtures:
                yield "fixture", fixture.key, fixture.point
            if run.area in self.slots.side_entries and not any(f.key == "side_exit" for f in room.fixtures):
                yield "fixture", "side_exit", self.slots.side_entries[run.area]
            if self.fixture_is_available(run.goal):
                yield "fixture", run.goal, room.story_point
        yield from self.encounters.targets()
        yield from self.encounters.followups()
        for cache in run.caches:
            if cache.area == run.area and not cache.taken:
                yield "cache", cache.id, cache.position
        for key, npc in nearby_targets(run, run.area):
            if not run.outbreak or npc.status == "passing" or (key.startswith("enc_") and npc.status in ("waiting", "disguised")):
                continue
            if not npc.infected:
                yield "actor", key, npc.position

    def blocked_door(self, gate):
        area, _, side = gate.partition("/")
        outdoors = self.slots.side_exits[area] if side else self.slots.doors[area]
        return any(actor.guard_door == gate and actor.status == "hostile" and not actor.stunned
                   and actor.area == "campus" and distance(outdoors, actor.position) < 51
                   for actor in self.run_state.actors.values())

    def nearest(self):
        current = self.run_state.position
        return min(
            (candidate for candidate in self.interactions()
             if self.fixture_is_available(candidate[1])
             and distance(current, candidate[2]) <= (143 if candidate[1].startswith("lure-") else 63 if candidate[0] == "door" else 46)
             and visible(current, candidate[2], self.collides)),
            key=lambda candidate: (distance(current, candidate[2]), candidate[0] != "event_point"),
            default=None,
        )

    def label(self, kind, key):
        if kind == "door":
            area, _, side = key.partition("/")
            place = self.campus_name(area)
            if self.blocked_door(key):
                return self.tr("event.door_blocked")
            if area in self.run_state.locked:
                return self.tr("fixture.locked_door", place=place)
            return self.tr("fixture.side_door", place=place) if side else place
        if kind == "event_point":
            return self.tr("fixture." + key)
        if kind == "encounter":
            return self.tr(self.encounters.title(self.run_state.encounters[key]))
        if kind == "actor":
            return self.actor_name(key)
        if key.startswith("lure-"):
            key = "mimic"
        if kind == "cache":
            cache = next(cache for cache in self.run_state.caches if cache.id == key)
            if cache.item == "bike":
                return self.tr("fixture.unlock_bike")
            return self.tr("fixture.search_" + cache.container)
        if key in ("exit", "side_exit"):
            gate = self.run_state.area + ("/side" if key == "side_exit" else "")
            if self.blocked_door(gate):
                return self.tr("event.door_blocked")
        return self.tr(f"{kind}.{key}")

    def show(self, title, text, options=(), *, speaker="", quote=None, encounter=False, **values):
        self.card = title, text
        self.card_values = values
        self.card_speaker = speaker
        self.card_quote = self.tr(quote) if quote else ""
        self.card_event = encounter
        self.options = options
        self.scene = "card"

    def actor_name(self, key):
        event = self.encounters.encounter_for_actor(key) if key.startswith("enc_") else None
        return self.encounters.person_name(key, event) if event else self.tr("actor." + key)

    def interact(self):
        if self.run_state.infection_until:
            return
        match = self.nearest()
        if not match:
            return
        kind, key, spot = match
        state = self.run_state
        if kind == "door":
            area, _, side = key.partition("/")
            if self.blocked_door(key):
                self.notify("event.door_blocked")
                return
            if area in state.locked:
                if not state.pack["key"]:
                    self.notify("event.need_key")
                    return
                state.locked.remove(area)
                self.notify("event.unlocked_door")
            room = self.rooms[area]
            destination = self.slots.side_entries[area] if side else room.entry
            self.travel(area, spot, destination, room.hit, key)
        elif kind == "encounter":
            self.encounters.open(key)
        elif kind == "event_point":
            self.encounters.complete(key)
        elif kind == "cache":
            cache = next(cache for cache in state.caches if cache.id == key)
            if cache.item == "bike" and not state.pack["key"]:
                self.notify("event.need_key")
                return
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
            gate = state.area + ("/side" if key == "side_exit" else "")
            if self.blocked_door(gate):
                self.notify("event.door_blocked")
                return
            self.travel("campus", match[2], outside, self.world.collides,
                        gate)
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
                state.add_gear("water")
                self.notify("event.found", item=self.tr("gear.water"))
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
                      speaker=self.encounters.person_name(key, event))
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
            elif not state.pack["food"]:
                self.notify("exp.missing", item=self.tr("gear.food"))
            else:
                state.pack["food"] -= 1
                state.add_gear("water")
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

    def fit_words(self, text, point, size, width, color=PAPER, bold=False, anchor="topleft"):
        while size > 11 and self.fonts.get(size, bold).size(text)[0] > width:
            size -= 1
        return self.words(text, point, size, color, bold, anchor)

    def lines(self, text, point, size, width, color=PAPER):
        x, y = point
        for line in self.fonts.wrapped(text, size, width):
            self.words(line, (x, y), size, color)
            y += size + 8
        return y

    def panel(self, rect, color=PANEL, border=LINE, radius=10):
        cut_panel(self.canvas, rect, color, border, radius//2)

    def frame(self, rect, title, *, accent=GOLD, title_size=30):
        rect = pygame.Rect(rect)
        self.panel(rect.move(0, 6), (7, 12, 19), (7, 12, 19))
        self.panel(rect, INK)
        pygame.draw.rect(self.canvas, accent, (rect.x+19, rect.y, 48, 3))
        pygame.draw.line(self.canvas, LINE, (rect.x+22, rect.y+63), (rect.right-22,rect.y+63))
        self.fit_words(title, (rect.x+24,rect.y+32), title_size, rect.width-48, PAPER, True, "midleft")
        return rect

    def shade(self, color=(12, 19, 22, 192)):
        self.overlay.fill(color)
        self.canvas.blit(self.overlay, (0, 0))

    def button(self, rect, label, action, mouse, *, accent=False, enabled=True, glyph=None, keycap=None):
        rect = pygame.Rect(rect)
        hover = enabled and rect.collidepoint(mouse)
        fill = ((255, 204, 145) if hover else GOLD) if accent else (
            (38, 55, 48) if hover else (25, 39, 36) if enabled else (18, 28, 27))
        border = GOLD if accent else (108,139,126) if hover else LINE
        self.panel(rect, fill, border)
        color = INK if accent else PAPER if enabled else (115, 132, 123)
        if glyph:
            icon(self.canvas, glyph, (rect.x+26, rect.centery), color)
            self.fit_words(label, (rect.x+50, rect.centery), 20, rect.width-68, color, accent, "midleft")
            if hover and not accent:
                pygame.draw.rect(self.canvas, BLUE, (rect.x, rect.y+11, 2, rect.height-22))
        elif keycap:
            key_width = 23 if len(keycap)==1 else len(keycap)*8+13
            self.interface.keycap(self.canvas, keycap, (rect.x+8, rect.centery-11,key_width,22))
            self.fit_words(label, (rect.x+17+key_width, rect.centery), 16,
                           rect.width-key_width-24, color, accent, "midleft")
        else:
            self.fit_words(label, rect.center, 18, rect.width-18, color, accent, "center")
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
        tick = pygame.time.get_ticks()
        self.draw_menu_backdrop(tick)
        self.draw_rain(tick, heavy=True)
        if self.scene == "title":
            self.panel((0,0,1280,57), (16,25,24), LINE, radius=0)
            pygame.draw.rect(self.canvas,GOLD,(41,12,32,32),1,border_radius=2)
            icon(self.canvas,"campus",(57,28),GOLD,23)
            self.fit_words(self.tr("ui.brand"),(85,28),18,350,PAPER,True,"midleft")
            self.words(self.tr("ui.setting_campus"), (48, 187), 16, GOLD, True)
            self.interface.heading(self.canvas,self.tr("ui.brand"),(43,213),111,665,self.localizer.language)
            self.fit_words(self.tr("ui.title"), (48, 343), 35, 580, GOLD, True)
            self.lines(self.tr("ui.title_hook"), (49, 403), 18, 406, PAPER)
            for i, (label, action, glyph) in enumerate((("new", "customize", "start"),
                    ("continue", "continue", "resume"), ("settings","settings","settings"), ("quit","quit","quit"))):
                self.button_key((48+236*(i%2), 494+58*(i//2), 227, 47), label, action, mouse, glyph=glyph,
                                accent=i==0, enabled=action!="continue" or self.resume_run is not None)
            pygame.draw.line(self.canvas,(90,107,96),(42,653),(1238,653))
            icon(self.canvas,"rain",(53,678),GOLD,17)
            self.fit_words(self.tr("ui.title_weather"), (69, 678), 15, 370, PAPER, anchor="midleft")
            self.fit_words(self.tr("ui.unofficial"), (1238, 678), 15, 590, MUTED, anchor="midright")
        elif self.scene == "confirm":
            self.shade()
            self.frame((332, 208, 616, 298), self.tr("ui.new"))
            self.lines(self.tr("ui.replace"), (374, 314), 21, 530)
            self.button_key((374, 425, 240, 48), "back", "cancel_profile", mouse)
            self.button_key((661, 425, 239, 48), "new", "confirm", mouse, accent=True)
        else:
            self.shade()
            self.frame((220, 88, 840, 545), self.tr("ui.profile"))
            self.panel((257, 171, 257, 403), PANEL)
            for y in range(196, 555, 27):
                pygame.draw.line(self.canvas, (37,53,64), (270,y), (500,y))
            pygame.draw.line(self.canvas, (46,65,77), (385,188), (385,557))
            portrait = self.world.characters.sprite("down", 0, self.profile.appearance, preview=True)
            portrait = pygame.transform.smoothscale_by(portrait,1.48)
            pygame.draw.ellipse(self.canvas, (13, 23, 31), (322, 521, 125, 19))
            self.canvas.blit(portrait, portrait.get_rect(midbottom=(385, 528)))
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

    def draw_menu_backdrop(self, tick):
        if self.interface.backdrop is not None:
            self.canvas.blit(self.interface.backdrop, (0, 0))
        else:
            point = self.slots.lake
            camera = self.world.camera_for(point[0]+180, point[1]-38)
            self.world.draw_view(self.canvas,camera,(),self.paper_actor(point,"right"),False,tick)
        self.canvas.blit(self.interface.title_shade, (0, 0))

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
        self.weather_fx("rain", i in (1, 2), focus, tick, intro=True)
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
        self.weather_fx("rain", True, point - camera.topleft, tick, intro=True)
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
            self.weather_fx(state.weather, state.night, Vector2(state.position)-offset, tick, blackout=True)
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
        for projectile in state.projectiles:
            if projectile.area == state.area and (not outdoor or self.lit_at(projectile.position)):
                pos = Vector2(projectile.position) - offset - (0, 16)
                pygame.draw.line(self.canvas, RED if projectile.contaminated else GOLD,
                                 pos - Vector2(projectile.velocity).normalize()*14, pos, 2)
                pygame.draw.circle(self.canvas, PAPER, pos, 4)
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
            if kind == "cache":
                cache = next((cache for cache in state.caches if cache.id == key), None)
                if cache and cache.item == "bat":
                    pygame.draw.line(self.canvas, GOLD, position+(8,-10), position+(-8,10), 5)
                elif cache and cache.container == "dropped_key":
                    self.gear_icon("key", (position.x, position.y-4), GOLD)
            elif kind == "event_point":
                pygame.draw.circle(self.canvas, BLUE, position, 10, 2)
            elif key in STORY_STEPS:
                x, y = round(position.x), round(position.y)
                pygame.draw.polygon(self.canvas, INK, ((x,y-11),(x+11,y),(x,y+11),(x-11,y)))
                pygame.draw.polygon(self.canvas, GOLD, ((x,y-10),(x+10,y),(x,y+10),(x-10,y)), 2)
            elif kind not in ("actor", "cache"):
                color = GOLD if current and current[1] == key else (218, 219, 190)
                pygame.draw.circle(self.canvas, color, position, 6, 2)
        if current:
            label = self.label(*current[:2])
            width = min(650, self.fonts.get(18, True).size(label)[0]+68)
            left = 640-width//2
            self.panel((left, 568, width, 42), INK, LINE)
            self.interface.keycap(self.canvas, "E", (left+9,576,26,26), selected=True)
            self.fit_words(label, (left+49,589), 18, width-60, PAPER, True, "midleft")
        if pygame.time.get_ticks() < self.bat_at and (not outdoor or self.lit_at(state.position)):
            factor = 1-((self.bat_at-pygame.time.get_ticks())/450)
            frame = min(4, int(factor*5))
            angle = (-55, -27, 0, 28, 55)[frame]
            direction = Vector2(FACING[state.facing]).rotate(angle)
            start = Vector2(state.position)-offset+(0,-15)
            pygame.draw.line(self.canvas, GOLD, start+direction*22, start+direction*57, 5)
        if state.infection_until:
            remaining = max(0, state.infection_until - state.elapsed)
            self.shade((67, 22, 31, min(180, round((1.35 - remaining) * 140))))
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
        if enemy.concealed:
            return
        if enemy.stunned:
            self.words('✦', (x, y-44), 19, GOLD, True, 'center')
        elif enemy.reveal or enemy.windup:
            pygame.draw.arc(self.canvas, RED, (x-24, y-15, 48, 27), 0, math.tau, 4)
            self.words('!' if not enemy.throw_target else '»', (x, y-79), 21, RED, True, 'center')
        elif enemy.chasing and distance(enemy.position, self.run_state.position) <= 182:
            kind = enemy.kind if enemy.kind in KINDS else 'hunter'
            self.words(self.tr('infected.' + kind), (x, y-76), 13, KINDS[kind][-1], True, 'midbottom')

    def lit_at(self, point):
        state = self.run_state
        return not state.night or distance(point, state.position) <= NIGHT_VISION

    def draw_rain(self, tick, *, heavy=False):
        self.overlay.fill((0, 0, 0, 0))
        for i in range(180 if heavy else 86):
            layer = i % 3
            x = (i * 377 - int(tick * (.06 + layer * .03))) % (SIZE.width+44)
            y = (i * 137 + int(tick * (.38 + layer * .20))) % (SIZE.height+36) - 22
            length = 8 + layer * 9
            pygame.draw.aaline(self.overlay, (188, 216, 213, 57 + layer * 42),
                               (x, y), (x - length * .15, y + length))
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

    def weather_fx(self, weather, night, focus, tick, intro=False, *, blackout=False):
        if night and blackout:
            self.overlay.fill((13, 26, 41, 210))
            pool = self.ambient_night()
            self.overlay.blit(pool, pool.get_rect(center=focus), special_flags=pygame.BLEND_RGBA_MIN)
            self.canvas.blit(self.overlay, (0, 0))
        elif night or weather in ("rain", "cloud"):
            self.shade((16, 29, 44, 119 if night else 37 if weather == "rain" else 21))
        if weather == "rain":
            self.draw_rain(tick, heavy=intro)

    def draw_hud(self, mouse):
        state = self.run_state
        self.panel((20, 19, 290, 170), INK)
        if state.area in STORY_ROOMS:
            place = self.tr("location." + state.area)
        elif state.area != "campus":
            place = self.campus_name(state.area)
        else:
            place = self.tr("weather." + state.weather)
        phase = "outbreak" if state.outbreak else "blackout" if state.blackout else "clock"
        phase_color = RED if state.outbreak else GOLD if state.blackout else BLUE
        pygame.draw.rect(self.canvas, phase_color, (32,19,40,2))
        pygame.draw.circle(self.canvas, phase_color, (37,44), 3)
        self.fit_words(self.tr("ui.status_"+phase), (48,44), 14, 136, phase_color, True, "midleft")
        self.interface.mono(self.canvas, state.clock, (288,46), 31, PAPER, "midright")
        self.fit_words(place, (35,70), 17, 250, PAPER, True, "midleft")
        pygame.draw.line(self.canvas,LINE,(33,89),(297,89))
        for y, key, value, color in ((104,"hunger",state.hunger,GOLD), (131,"thirst",state.thirst,BLUE),
                                     (158,"stamina",state.stamina,(171,207,154))):
            self.fit_words(self.tr("ui."+key), (35,y+5), 14, 84, MUTED, anchor="midleft")
            pygame.draw.rect(self.canvas,TRACK,(122,y,131,9))
            pixels = round(131*max(0,min(100,value))/100)
            fill = RED if value < 23 else color
            if pixels:
                pygame.draw.rect(self.canvas,fill,(122,y,pixels,9))
            for mark in (148,174,201,227):
                pygame.draw.line(self.canvas, INK, (mark,y), (mark,y+8))
            self.interface.mono(self.canvas,math.ceil(value),(288,y+5),14,PAPER,"midright")
        self.button_key((993, 19, 122, 40), "map_short", "map", mouse, keycap="M")
        self.button_key((1125, 19, 135, 40), "journal_short", "journal", mouse, keycap="Q")
        if state.team:
            self.panel((993, 70, 267, 39+27*len(state.team)), INK)
            self.words(self.tr("ui.team"), (1009, 80), 13, MUTED, True)
            for i, key in enumerate(state.team):
                actor = state.actors[key]
                label = self.actor_name(key)
                if actor.status == "bitten":
                    label += f"  ·  {self.tr('ui.infected')} {math.ceil(actor.infection)}"
                color = RED if actor.status=="bitten" else PAPER
                pygame.draw.circle(self.canvas, color, (1013,114+27*i), 3)
                self.fit_words(label, (1025, 114+27*i), 15, 223, color, anchor="midleft")
        top = 19
        if self.persistent_hint:
            top = self.hud_notice(self.persistent_hint, top, GOLD)
        if self.toast and pygame.time.get_ticks() < self.toast_until:
            self.hud_notice(self.toast, top, BLUE)
        if state.injury_until > state.elapsed:
            self.panel((20,199,290,31),INK,(135,72,63))
            self.fit_words(self.tr("ui.injury",seconds=math.ceil(state.injury_until-state.elapsed)),
                           (34,214),14,258,RED,True,"midleft")
        left = (1280 - (len(GEAR)*112+17)) // 2
        self.panel((left, 616, len(GEAR)*112+17, 98), INK)
        for i, item in enumerate(GEAR):
            rect = pygame.Rect(left+9+112*i, 624, 104, 60)
            self.hotbar.append(rect)
            select = i == state.selected
            self.panel(rect, (57,44,33) if select else (37,53,46) if rect.collidepoint(mouse) else PANEL,
                       GOLD if select else LINE)
            if select:
                pygame.draw.rect(self.canvas,GOLD,(rect.x+8,rect.y,rect.width-16,2))
            self.interface.keycap(self.canvas,str(i+1),(rect.x+5,rect.y+5,19,18),selected=select)
            color = PALETTE[i] if state.pack[item] else (111,135,147)
            self.gear_icon(item, (rect.centerx, rect.y+24), color)
            self.fit_words(self.tr("gear."+item), (rect.centerx,rect.bottom-5), 14, 92,
                           PAPER if state.pack[item] or select else MUTED, anchor="midbottom")
            amount = str(state.pack[item])
            self.interface.mono(self.canvas,amount,(rect.right-8,rect.y+13),14,color,"midright")
        self.fit_words(self.tr("gear_tip." + GEAR[state.selected]), (640,699), 14, 510, PAPER, anchor="center")
        if state.area == "campus" and state.night:
            y = 243 if state.injury_until > state.elapsed else 199
            self.panel((20,y,290,30),INK)
            self.fit_words(self.tr("ui.night_map"), (34,y+15), 14,262, MUTED, anchor="midleft")

    def hud_notice(self, text, y, color):
        lines = self.fonts.wrapped(text, 16, 526)
        height = max(40, 20*len(lines)+15)
        self.panel((354, y, 572, height), INK)
        pygame.draw.rect(self.canvas,color,(355,y+8,2,height-16))
        for i,line in enumerate(lines):
            self.words(line,(372,y+10+20*i),16,PAPER)
        return y+height+7

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
        elif item == 'key':
            pygame.draw.circle(self.canvas, color, (x-6,y-3), 5, 3)
            pygame.draw.line(self.canvas, color, (x-2,y), (x+8,y+8), 3)
            pygame.draw.line(self.canvas, color, (x+4,y+4), (x+9,y), 2)
        else:
            pygame.draw.ellipse(self.canvas,color,(x-12,y-7,24,15))
            pygame.draw.line(self.canvas,INK,(x-7,y+2),(x+7,y+2),2)

    def draw_pause(self, mouse):
        self.shade()
        self.frame((424, 132, 432, 465), self.tr("ui.pause"))
        for i,(label,action,glyph) in enumerate((("resume_game","play","start"),("settings","settings","settings"),
                                                   ("save_title","title","resume"),("quit","quit","quit"))):
            self.button_key((466,225+i*73,348,55),label,action,mouse,accent=i==0,glyph=glyph)
        self.fit_words(self.tr("ui.controls"),(640,548),14,340,MUTED,anchor="center")

    def draw_settings(self, mouse):
        self.draw_menu_backdrop(pygame.time.get_ticks())
        self.shade((9,16,23,133))
        self.frame((310, 111, 660, 488), self.tr("ui.settings"))
        rows = (
            ("setting_language", "繁體中文" if self.localizer.language=="zh_TW" else "English", "language"),
            ("setting_display", self.tr("ui.setting_full" if self.fullscreen else "ui.setting_window"), "screen"),
            ("setting_audio", self.tr("ui.state_on" if self.profile.sound else "ui.state_off"), "sound"),
            ("setting_scares", self.tr("ui.state_on" if self.profile.scares else "ui.state_off"), "scares"),
        )
        for i,(label,value,action) in enumerate(rows):
            y = 194+i*77
            self.panel((338,y,604,64),PANEL)
            self.fit_words(self.tr("ui."+label),(358,y+31),18,221,PAPER,True,"midleft")
            self.button((626,y+9,295,46),value,action,mouse,keycap="F11" if action=="screen" else None)
        self.button_key((626, 522, 295, 47), "back", "settings_back", mouse, accent=True)

    def draw_card(self, mouse):
        if self.card_event:
            self.draw_encounter(mouse)
            return
        self.shade((10, 17, 23, 148))
        title, text = self.card
        self.frame((230, 175, 820, 488), self.tr(title), accent=BLUE)
        content = self.tr(text, **self.card_values)
        text_size = 21 if len(self.fonts.wrapped(content, 21, 732)) <= 4 else 18
        y = self.lines(content, (273,263), text_size, 738)
        speaker = "  ·  ".join(part for part in (self.card_speaker,self.card_quote) if part)
        if speaker:
            y = min(y+9,386)
            pygame.draw.rect(self.canvas, BLUE, (274,y+3,2,18))
            self.fit_words(speaker,(285,y+12),16,718,MUTED,False,"midleft")
        count = len(self.options)
        columns = 1 if count <= 3 else 2
        choice_width = 732 if columns==1 else 359
        for i, action in enumerate(self.options):
            key = action.split("/")[0]
            label = self.encounters.option_label(action) if action.startswith("event_") else self.tr("choice."+key)
            self.button((274+i%columns*373, 426+i//columns*55, choice_width, 46),
                        label, "choice/"+action, mouse, keycap=str(i+1))
        self.button_key((784, 607, 222, 38), "close","play", mouse, accent=not self.options)

    def draw_field_header(self, screen):
        state = self.run_state
        self.panel((0,0,1280,68), (16,25,24), LINE, radius=0)
        self.interface.mono(self.canvas,state.clock,(39,33),31,PAPER,"midleft")
        self.fit_words(self.tr("ui."+screen),(145,33),21,325,PAPER,True,"midleft")
        phase = "outbreak" if state.outbreak else "blackout" if state.blackout else "power"
        phase_color = RED if state.outbreak else GOLD if state.blackout else (165,206,183)
        self.fit_words(self.tr("ui.status_"+phase),(845,33),15,245,phase_color,anchor="midright")
        for x, key, value, color in ((885,"hunger",state.hunger,GOLD),
                                     (1064,"thirst",state.thirst,BLUE)):
            self.fit_words(self.tr("ui."+key),(x,33),14,80,MUTED,anchor="midleft")
            pygame.draw.rect(self.canvas,TRACK,(x+82,30,83,6),border_radius=2)
            fill = round(83 * max(0,min(100,value)) / 100)
            if fill:
                pygame.draw.rect(self.canvas,RED if value < 23 else color,
                                 (x+82,30,fill,6),border_radius=2)

    def draw_encounter(self, mouse):
        state = self.run_state
        art_rect = pygame.Rect(55, 116, 432, 500)
        if state.area == "campus" and self.interface.encounter_art is not None:
            art = self.interface.encounter_art
        else:
            crop = pygame.Rect(0,0,484,560)
            crop.center = state.position if state.area != "campus" else SIZE.center
            crop.clamp_ip(SIZE)
            art = pygame.transform.smoothscale(self.canvas.subsurface(crop),art_rect.size)
        self.shade((9,17,16,207))
        self.draw_field_header("encounter_screen")
        self.panel((36, 96, 1208, 558), PANEL, LINE, radius=6)
        self.canvas.blit(art,art_rect)
        self.canvas.blit(self.interface.encounter_shade,art_rect)
        place = self.tr("ui.setting_campus") if state.area == "campus" else self.campus_name(state.area)
        pygame.draw.rect(self.canvas,RED,(73,542,2,50))
        self.fit_words(place,(88,546),15,369,GOLD,True)
        if self.card_speaker:
            self.interface.heading(self.canvas,self.card_speaker,(88,569),27,369,self.localizer.language)
        title, text = self.card
        self.words(self.tr("ui.event_choices" if self.options else "ui.event_outcome"),(517,130),15,GOLD,True)
        self.interface.heading(self.canvas,self.tr(title),(517,159),41,686,self.localizer.language)
        content = self.tr(text, **self.card_values)
        size = 20
        while size > 14 and len(self.fonts.wrapped(content,size,676)) * (size+8) > 193:
            size -= 1
        body_bottom = self.lines(content,(519,223),size,676,PAPER)
        choice_top = min(426,max(315,body_bottom+21))
        columns = 2 if len(self.options) > 3 else 1
        for i, action in enumerate(self.options):
            width = 676 if columns == 1 else 332
            x = 518 + (i % columns) * 344
            y = choice_top + (i // columns) * 52
            label = self.encounters.option_label(action)
            self.button((x,y,width,45),label,"choice/"+action,mouse,keycap=str(i+1))
        if not self.options:
            self.button_key((518,575,246,42),"map_short","event_map",mouse,keycap="M")
        self.button_key((980,591,214,42),"close","play",mouse,accent=not self.options)

    def draw_journal(self, mouse):
        self.shade()
        self.frame((114, 65, 1052, 590), self.tr("ui.journal_title"))
        state = self.run_state
        keys = [key for key in state.observations if key in OBSERVATIONS]
        self.panel((140,151,314,423),PANEL)
        self.panel((478,151,660,423),PANEL)
        self.words(self.tr("ui.journal_goal"),(161,173),20,GOLD,True)
        self.words(self.tr("ui.journal_clues"),(499,173),20,BLUE,True)
        objective_y = 225
        if state.outbreak:
            stop = tuple(state.route).index(state.goal) + 1
            self.fit_words(self.tr("route.progress",stop=stop,total=len(state.route)),
                           (162,225),17,266,MUTED,True)
            for i in range(len(state.route)):
                pygame.draw.rect(self.canvas, GOLD if i < stop else TRACK, (163+i*30,256,23,4))
            objective_y = 282
        self.lines(self.route_hint(),(162,objective_y),18,263)
        if keys:
            entries = [(self.tr("clue."+key+".title"),self.tr("clue."+key+".text")) for key in keys[-4:]]
            size = 17
            while size > 13 and sum(32+(size+8)*len(self.fonts.wrapped(text,size,598)) for _,text in entries) > 349:
                size -= 1
            y = 216
            for title,text in entries:
                self.fit_words(title,(501,y),17,600,PAPER,True)
                y = self.lines(text,(501,y+24),size,598,MUTED)+8
        else:
            self.lines(self.tr("ui.empty_journal"),(501,219),18,594,MUTED)
        self.button_key((140,592,242,42), "event_log", "event_log", mouse)
        self.button_key((914,592,224,42), "back","play",mouse,accent=True)

    def draw_event_log(self, mouse):
        self.shade()
        self.frame((213, 76, 854, 567), self.tr("ui.event_log"), accent=BLUE)
        encounters = self.run_state.encounters.values()
        history = sorted((event for event in encounters if event.clock), key=lambda event: event.clock, reverse=True) if self.run_state.outbreak else []
        page_count = max(1, math.ceil(len(history) / 5))
        self.event_page = max(0, min(self.event_page, page_count - 1))
        if not history:
            self.lines(self.tr("exp.log_empty"), (254, 182), 20, 760, MUTED)
        page = history[self.event_page*5:self.event_page*5+5]
        for i, event in enumerate(page):
            y = 174 + i*76
            h, m = divmod(event.clock % 1440, 60)
            self.interface.mono(self.canvas,f"{h:02d}:{m:02d}",(254,y+11),17,BLUE,"midleft")
            name = self.tr(self.encounters.title(event)) + "  ·  " + event.name(self.localizer.language)
            self.fit_words(name, (323,y),19,701,PAPER,True)
            desc = self.encounters.result_key(event) if event.outcome else "exp.log_" + event.status
            self.lines(self.tr(desc), (323,y+27), 15, 690, MUTED)
            if i < len(page)-1:
                pygame.draw.line(self.canvas,LINE,(253,y+65),(1026,y+65))
        self.button_key((254, 574, 120, 38), "map_previous", "event_previous", mouse, enabled=self.event_page > 0)
        self.words(f"{self.event_page+1} / {page_count}", (418, 594), 15, MUTED, False, "center")
        self.button_key((463, 574, 120, 38), "map_next", "event_next", mouse, enabled=self.event_page+1 < page_count)
        self.button_key((808, 574, 215, 38), "back", "journal", mouse, accent=True)

    def open_map(self, return_to="play"):
        self.map_return = return_to
        self.scene = "map"

    def map_colors(self):
        state = self.run_state
        return FIELD_MAP if state and (state.blackout or state.outbreak) else DIRECTORY

    def map_layer(self):
        bounds = MAP_FOCUS if self.map_zoom else self.world_map_bounds
        scale = min((MAP_SHEET.width - 8) / bounds.width, (MAP_SHEET.height - 24) / bounds.height)
        size = round(bounds.width * scale), round(bounds.height * scale)
        rect = pygame.Rect((0,0), size)
        rect.center = MAP_SHEET.center
        colors = self.map_colors()
        cache_key = (self.map_zoom, colors)
        if cache_key not in self.maps:
            self.maps[cache_key] = campus_atlas(bounds, size, scale, colors)
        return self.maps[cache_key], bounds, rect, scale

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

    def map_marker_at(self, mouse, pins, bounds, rect, scale):
        pin = self.map_pin_at(mouse, pins)
        if pin is not None or not rect.collidepoint(mouse):
            return pin
        point = (Vector2(mouse) - rect.topleft) / scale + bounds.topleft
        return next((key for key, building in CAMPUS_BUILDINGS.items()
                     if key in pins and pygame.Rect(building["rect"].pixels()).collidepoint(point)), None)

    def change_map_page(self, delta):
        _, bounds, _, _ = self.map_layer()
        count = sum(bounds.collidepoint(point) for point in self.map_points.values())
        last_page = max(0, (count - 1) // MAP_PAGE_SIZE)
        self.map_page = max(0, min(self.map_page + delta, last_page))

    def pick_map_marker(self, mouse):
        _, bounds, rect, scale = self.map_layer()
        pins = self.map_pin_positions(bounds, rect, scale)
        key = self.map_marker_at(mouse, pins, bounds, rect, scale)
        if key is not None:
            self.map_selected = key
            self.map_page = list(pins).index(key) // MAP_PAGE_SIZE

    def draw_map(self, mouse):
        self.shade((9,17,16,222))
        self.draw_field_header("map_short")
        state = self.run_state
        colors = self.map_colors()
        image, bounds, map_rect, scale = self.map_layer()
        pygame.draw.rect(self.canvas,colors.paper,MAP_SHEET,border_radius=4)
        self.canvas.blit(image, map_rect)
        pygame.draw.rect(self.canvas,colors.curb,MAP_SHEET,1,border_radius=4)
        self.draw_atlas_labels(bounds,map_rect,scale,colors)
        pins = self.map_pin_positions(bounds, map_rect, scale)
        page_count = max(1, math.ceil(len(pins) / MAP_PAGE_SIZE))
        self.map_page = min(self.map_page, page_count - 1)
        start = self.map_page * MAP_PAGE_SIZE
        page = list(pins)[start:start + MAP_PAGE_SIZE]
        rows = {key: pygame.Rect(904, 166 + 31*i, 322, 27) for i, key in enumerate(page)}
        hovered_row = next((key for key, row in rows.items() if row.collidepoint(mouse)), None)
        highlighted = hovered_row or self.map_marker_at(mouse,pins,bounds,map_rect,scale) or self.map_selected

        def project(point):
            return (Vector2(point) - bounds.topleft) * scale + map_rect.topleft

        for key, pin in pins.items():
            if key in state.locked:
                pygame.draw.circle(self.canvas,colors.paper,pin,9)
                pygame.draw.circle(self.canvas,colors.alert,pin,9,1)
                icon(self.canvas,"lock",pin,colors.alert,14)
            else:
                pygame.draw.circle(self.canvas,colors.paper,pin,4)
                pygame.draw.circle(self.canvas,colors.ink,pin,2 if key in rows else 1)
        for point, time in self.map_sightings.values():
            if state.outbreak and state.elapsed - time <= SIGHTING_SECONDS and bounds.collidepoint(point):
                mark = project(point)
                pygame.draw.circle(self.canvas,colors.paper,mark,9)
                icon(self.canvas,"sighting",mark,colors.alert,17)
        if state.outbreak and highlighted in self.slots.side_exits:
            point = self.slots.side_exits[highlighted]
            if bounds.collidepoint(point):
                mark = project(point)
                pygame.draw.circle(self.canvas,colors.paper,mark,9)
                icon(self.canvas,"side",mark,colors.route,16)
        if state.outbreak and not state.ending:
            target = pins.get(state.goal_area)
            if state.goal_area in self.slots.outdoor_clues:
                outdoor_point = self.slots.outdoor_clues[state.goal_area]
                if bounds.collidepoint(outdoor_point):
                    target = project(outdoor_point)
            if target is not None:
                pygame.draw.circle(self.canvas,colors.paper,target,8)
                icon(self.canvas,"goal",target,colors.alert,24)
        point = state.position if state.area == "campus" else self.slots.doors[state.area]
        if bounds.collidepoint(point):
            pin = project(point)
            pygame.draw.circle(self.canvas,INK,pin,10)
            icon(self.canvas,"player",pin,PAPER,23)
        if waypoint := self.encounters.waypoint():
            area, point = waypoint
            if area != "campus":
                point = self.slots.doors[area]
            if bounds.collidepoint(point):
                pin = project(point)
                pygame.draw.circle(self.canvas,colors.paper,pin,9)
                icon(self.canvas,"waypoint",pin,colors.route,24)
        if highlighted in pins:
            pin = pins[highlighted]
            pygame.draw.circle(self.canvas,colors.ink,pin,11,2)
            name = self.campus_name(highlighted)
            if highlighted in state.locked:
                name = self.tr("fixture.locked_door",place=name)
            width = self.fonts.get(16, True).size(name)[0] + 22
            tag = pygame.Rect(0, 0, width, 27)
            tag.midbottom = (round(pin.x), round(pin.y)-12)
            tag.clamp_ip(MAP_SHEET.inflate(-8,-8))
            self.panel(tag, INK, GOLD, radius=6)
            self.words(name, tag.center, 16, PAPER, True, "center")
        self.panel((889,91,355,564),PANEL,LINE,radius=6)
        phase = "map_after" if state.outbreak else "map_blackout" if state.blackout else "map_before"
        self.fit_words(self.tr("ui."+phase),
                       (905,114),14,315,RED if colors is FIELD_MAP else (165,206,183),True,"midleft")
        self.interface.heading(self.canvas,self.tr("ui.landmarks"),(904,126),27,322,self.localizer.language)
        for key, row in rows.items():
            self.button(row, self.campus_name(key), "map_pin/" + key, mouse, accent=key == highlighted)
        self.button_key((904, 423, 98, 32), "map_previous", "map_previous", mouse, enabled=self.map_page > 0)
        self.words(f"{self.map_page + 1} / {page_count}", (1065, 439), 15, MUTED, False, "center")
        self.button_key((1128, 423, 98, 32), "map_next", "map_next", mouse, enabled=self.map_page + 1 < page_count)
        pygame.draw.line(self.canvas,LINE,(905,468),(1225,468))
        if state.outbreak:
            self.lines(self.route_hint(), (905, 481), 15, 315, PAPER)
        elif highlighted is None:
            self.lines(self.tr("ui.map_hint"),(905,481),15,315,MUTED)
        if highlighted in pins:
            self.fit_words(self.campus_name(highlighted),(905,571),16,315,GOLD,True,"midleft")
        self.button_key((904, 597, 152, 39), "full_map" if self.map_zoom else "route_map", "zoom", mouse)
        self.button_key((1066, 597, 160, 39), "back", "map_back", mouse, accent=True,keycap="M")
        self.draw_map_legend()

    def draw_atlas_labels(self, bounds, rect, scale, colors):
        title = "ui.map_field" if colors is FIELD_MAP else "ui.map_directory"
        pygame.draw.rect(self.canvas,colors.paper,(49,106,209,67),border_radius=3)
        self.words(self.tr("ui.campus_main"),(56,110),13,colors.ink,True)
        self.interface.heading(self.canvas,self.tr(title),(55,131),29,199,self.localizer.language,colors.ink)
        self.interface.mono(self.canvas,"N",(845,110),13,colors.ink,"center")
        pygame.draw.polygon(self.canvas,colors.ink,((845,121),(835,149),(845,144),(855,149)))
        pygame.draw.polygon(self.canvas,colors.paper,((845,127),(845,141),(839,144)))
        lake = next(water for water in WATERS if water["id"] == "success_lake_water")
        shore = [Vector2(point) * TILE for point in lake["points"]]
        center = sum(shore,Vector2()) / len(shore)
        occupied = [pygame.Rect(49,106,209,67), pygame.Rect(822,98,49,55)]
        for label, point, offset in ((self.localizer.t("zone.success_lake"),center,(9,0)),
                                     (self.campus_name("lawn"),self.slots.lawn,(0,-13)),
                                     (self.campus_name("gate"),self.slots.start,(-3,-16))):
            if bounds.collidepoint(point):
                position = (Vector2(point)-bounds.topleft)*scale + rect.topleft + offset
                occupied.append(self.fit_words(label,position,14,139,colors.ink,True,"center").inflate(8,4))
        if not self.map_zoom:
            return
        for key in ("education","main_library","general_4","xin_hall","ren_hall","li_hall","yi_hall"):
            footprint = pygame.Rect(CAMPUS_BUILDINGS[key]["rect"].pixels())
            name = self.campus_name(key)
            label = pygame.Rect((0,0),self.fonts.get(12,True).size(name))
            position = (Vector2(footprint.midtop) - bounds.topleft) * scale + rect.topleft
            label.midbottom = position.x, position.y - 2
            if rect.contains(label) and label.collidelist(occupied) < 0:
                pygame.draw.rect(self.canvas,colors.paper,label.inflate(4,1),border_radius=2)
                self.words(name,label.topleft,12,colors.ink,True)
                occupied.append(label.inflate(8,4))

    def draw_map_legend(self):
        self.panel((36,670,1208,35),PANEL)
        keys = [("player","map_you",PAPER),("goal","map_goal",GOLD),("waypoint","map_waypoint",BLUE),
                ("lock","map_locked",RED)]
        if self.run_state.outbreak:
            keys += [("side","map_side",BLUE),("sighting","map_seen",RED)]
        spacing = 1180 // len(keys)
        for i,(glyph,label,color) in enumerate(keys):
            x = 55+i*spacing
            icon(self.canvas,glyph,(x,687),color,18)
            self.fit_words(self.tr("ui."+label),(x+15,687),14,spacing-31,MUTED,anchor="midleft")

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
        if state.ending:
            title, description = "ending.title", "ending.text"
        else:
            title, description = "death.title", "death."+state.death
        self.frame((282, 143, 716, 449), self.tr(title), accent=RED, title_size=34)
        name = self.profile.name or self.tr("ui.default_name")
        y = self.lines(self.tr(description, name=name), (329,252), 21, 615)
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
