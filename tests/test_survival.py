from collections import deque
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

from nthu_adventure.survival import Actor, CAMPUS_BUILDINGS, ENDING, GEAR, INFECTION_SECONDS, KINDS, MUTATIONS, Projectile, Run, RunStore, body, simulate, use_gear
from nthu_adventure.survival_game import MAP_PAGE_SIZE, Game


def walkable_steps(start, goal, collision, step=5):
    """Find a route using the same player collision box as real movement."""
    start = tuple(round(x) for x in start)
    queue = deque([start])
    seen = {start}
    while queue:
        x, y = queue.popleft()
        if pygame.Vector2(x, y).distance_to(goal) < 9:
            return True
        for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
            neighbor = x+dx, y+dy
            if neighbor not in seen and not collision(body(neighbor)):
                queue.append(neighbor)
                seen.add(neighbor)
    return False


class LastReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.game = Game(Path(cls.temp.name))
        cls.addClassCleanup(cls.temp.cleanup)
        cls.addClassCleanup(pygame.quit)

    def setUp(self):
        self.game.begin(400)
        self.game.finish_intro()
        self.game.localizer.set_language("zh_TW")

    def test_generation_has_all_types_and_randomized_accessible_caches(self):
        g = self.game
        first = g.slots.new(111)
        other = g.slots.new(222)
        repeat = g.slots.new(111)
        self.assertEqual([c.position for c in first.caches], [c.position for c in repeat.caches])
        self.assertNotEqual([c.position for c in first.caches], [c.position for c in other.caches])
        self.assertNotEqual(first.actors["enemy_0"].position, other.actors["enemy_0"].position)
        self.assertEqual({c.item for c in first.caches[:4]}, {"water", "food", "bat"})
        self.assertEqual({a.kind for a in first.actors.values() if a.infected}, set(KINDS))
        self.assertGreater(sum(a.infected for a in first.actors.values()), 33)
        g.run_state.position = next(a.position for a in g.run_state.actors.values() if a.infected)
        g.draw((0, 0))
        self.assertEqual({cache.area for cache in first.caches}, set(g.rooms) | {"campus"})
        self.assertGreaterEqual(sum(bool(cache.item) for cache in first.caches), 40)
        self.assertEqual({cache.area for cache in first.caches if cache.item}, set(g.rooms) | {"campus"})
        self.assertTrue(any(not cache.item for cache in first.caches))
        for area, room in g.rooms.items():
            cache = next(cache for cache in first.caches if cache.area == area)
            self.assertFalse(room.hit(body(cache.position)))
            self.assertTrue(walkable_steps(room.entry, cache.position, room.hit))
        for point in [*g.slots.doors.values(), *g.slots.incidents.values(), *g.slots.outdoor_clues.values()]:
            self.assertFalse(g.world.collides(body(point)))
            self.assertLess(min(pygame.Vector2(point).distance_to(cell) for cell in g.slots.reachable), 20)

    def test_interiors_and_interactions_reachable_through_actual_controls(self):
        g = self.game
        for room in g.rooms.values():
            points = {fixture.key: fixture.point for fixture in room.fixtures}
            points.update(story=room.story_point, event=room.event_point)
            for key, point in points.items():
                with self.subTest(area=room.key, fixture=key):
                    self.assertFalse(room.hit(body(point)))
                    self.assertTrue(walkable_steps(room.entry, point, room.hit))

    def test_complete_both_languages_solo_and_companion(self):
        g = self.game
        routes = []
        for seed, language in ((512, "zh_TW"), (735, "en")):
            with self.subTest(language=language):
                g.begin(seed)
                g.finish_intro()
                g.localizer.set_language(language)
                run = g.run_state
                run.start_outbreak()
                key_cache = next(c for c in run.caches if c.item == "key")
                self.assertNotIn(key_cache.area, run.locked)
                run.position = g.slots.doors[key_cache.area]
                g.interact()
                run.position = key_cache.position
                g.interact()
                self.assertEqual(run.pack["key"], 1)
                run.position = g.rooms[key_cache.area].entry
                g.interact()
                routes.append(dict(run.route))
                if language == "en":
                    run.position = g.slots.doors["education"]
                    g.interact()
                    run.position = run.actors["student"].position
                    g.interact()
                    g.action("choice/join/student")
                    self.assertEqual(run.team, ["student"])
                    run.position = g.rooms["education"].entry
                    g.interact()
                for step in run.route:
                    area = run.route[step]
                    self.assertEqual(run.goal, step)
                    self.assertIn(g.campus_name(area), g.route_hint())
                    if area in g.slots.outdoor_clues:
                        self.assertEqual(run.area, "campus")
                        run.position = g.slots.outdoor_clues[area]
                    else:
                        run.position = g.slots.doors[area]
                        g.key(pygame.K_e)
                        self.assertEqual(run.area, area)
                        run.position = g.rooms[area].story_point
                    g.key(pygame.K_e)
                    self.assertEqual(g.scene, "card")
                    self.assertNotIn("[survival.", g.tr(g.card[1], **g.card_values))
                    self.assertNotIn("{place}", g.tr(g.card[1], **g.card_values))
                    if step != "sealed":
                        if g.options:
                            original_route = run.route.copy()
                            g.key(pygame.K_2 if language == "en" else pygame.K_1)
                            if language == "en" and step == "echo_log":
                                self.assertNotEqual(run.route, original_route)
                        else:
                            g.key(pygame.K_RETURN)
                        self.assertIn(step, run.observations)
                        if area in g.rooms:
                            run.position = g.rooms[area].entry
                            g.interact()
                        self.assertEqual(run.area, "campus")
                        continue
                    g.key(pygame.K_2)
                    self.assertIsNone(run.ending)
                    self.assertEqual(g.scene, "play")
                    g.key(pygame.K_e)
                    g.key(pygame.K_1)
                    self.assertEqual(run.ending, ENDING)
                    self.assertEqual(g.scene, "ending")
                    g.draw((0, 0))
                    g.update(6)
                    g.draw((0, 0))
                    self.assertIsNone(g.store.load())
        self.assertNotEqual(routes[0], routes[1])

    def test_bat_stuns_drops_key_and_cannot_kill(self):
        game = self.game
        run = game.run_state
        bat = next(cache for cache in run.caches if cache.id == "campus/materials_lab_court/bat")
        self.assertEqual(bat.area, "campus")
        self.assertEqual(tuple(v // 32 for v in bat.position), (51, 42))
        run.position = (100, 100)
        run.facing = "right"
        run.add_gear("bat")
        enemy = Actor("hunter", (150, 100), status="hostile", carried_key=True)
        run.actors = {"target": enemy}
        for _ in range(4):
            enemy.position = (150, 100)
            self.assertEqual(use_gear(run, "bat", lambda _: False), "used_bat")
            self.assertGreater(enemy.position[0], 150)
            self.assertGreater(enemy.stunned, 0)
        self.assertEqual(use_gear(run, "bat", lambda _: False), "too_tired")
        self.assertEqual(enemy.status, "hostile")
        self.assertEqual(run.pack["bat"], 1)
        self.assertEqual(len([cache for cache in run.caches if cache.id == "drop/target"]), 1)

    def test_bite_transmission_and_full_restart(self):
        g = self.game
        run = g.run_state
        base = run.position
        run.actors = {
            "student": Actor("student", (base[0]+34, base[1]), status="joined", choice="join"),
            "attacker": Actor("hunter", (base[0]+37, base[1]), status="hostile", windup=.01, target="student"),
        }
        simulate(run, .02, pygame.Vector2(), False, lambda rect: False)
        self.assertEqual(run.actors["student"].status, "bitten")
        g.store.save(run)
        round_trip = g.store.load()
        self.assertEqual(round_trip.actors["student"].infection, INFECTION_SECONDS)
        run.actors["attacker"].area = "main_library"
        run.actors["student"].infection = .01
        simulate(run, .02, pygame.Vector2(), False, lambda rect: False)
        self.assertEqual(run.actors["student"].status, "turned")
        self.assertFalse(run.team)
        run.actors["student"].windup = .01
        run.actors["student"].target = "player"
        run.actors["student"].position = base
        g.update(.02)
        self.assertIsNone(run.death)
        self.assertGreater(run.infection_until, run.elapsed)
        g.update(1.36)
        self.assertEqual(run.death, "bite")
        self.assertEqual(g.scene, "death")
        self.assertIsNone(g.store.load())
        g.key(pygame.K_RETURN)
        self.assertNotEqual(run.seed, g.run_state.seed)
        self.assertEqual(g.run_state.position, g.slots.start)
        self.assertFalse(g.run_state.observations)
        self.assertTrue(g.run_state.intro)
        self.assertEqual(g.run_state.pack, dict.fromkeys(GEAR, 0))

    def test_weather_needs_and_pause(self):
        g = self.game
        run = g.run_state
        dt = .05
        base = run.position
        simulate(run, dt, pygame.Vector2(1,0), False, lambda _: False)
        normal = pygame.Vector2(run.position).distance_to(base)
        run.position = base
        run.observe("playback")
        simulate(run, dt, pygame.Vector2(1,0), False, lambda _: False)
        self.assertAlmostEqual(pygame.Vector2(run.position).distance_to(base), normal * .8)
        for need in ("hunger", "thirst"):
            g.begin(711)
            g.finish_intro()
            run = g.run_state
            setattr(run, need, .001)
            g.scene = "map"
            g.update(1)
            self.assertIsNone(run.death)
            g.scene = "play"
            g.update(.02)
            self.assertEqual(run.death, need)
            self.assertIsNone(g.store.load())

    def test_thrown_debris_causes_injury_and_contamination(self):
        direction = pygame.Vector2(1, 0)
        healthy = Run(1, (100, 100))
        injured = Run(1, (100, 100))
        injured.projectiles.append(Projectile("campus", (85, 100), (350, 0), False, .1, .1))
        self.assertIn("throw_injury", simulate(injured, .045, pygame.Vector2(), False, lambda _: False))
        self.assertEqual(injured.infection_until, 0)
        after = injured.position[0]
        simulate(injured, .1, direction, False, lambda _: False)
        simulate(healthy, .1, direction, False, lambda _: False)
        self.assertAlmostEqual(injured.position[0]-after, (healthy.position[0]-100)*.8)

        infected = Run(2, (100, 100))
        infected.projectiles.append(Projectile("campus", (85, 100), (350, 0), True, .1, .1))
        self.assertIn("throw_infected", simulate(infected, .045, pygame.Vector2(), False, lambda _: False))
        self.assertIsNone(infected.death)
        simulate(infected, 1.4, pygame.Vector2(), False, lambda _: False)
        self.assertEqual(infected.death, "contamination")

    def test_bicycle_and_blocked_side_exit_have_distinct_gates(self):
        game = self.game
        run = game.run_state
        bike = next(cache for cache in run.caches if cache.item == "bike")
        run.area, run.position = bike.area, bike.position
        game.interact()
        self.assertFalse(bike.taken)
        run.add_gear("key")
        game.interact()
        self.assertEqual(run.pack["bike"], 1)
        self.assertEqual(run.pack["key"], 1)

        building = "gym"
        run.area, run.position = building, game.slots.side_entries[building]
        gate = building + "/side"
        run.start_outbreak()
        run.actors = {"blocker": Actor("stalker", game.slots.side_exits[building], status="hostile", guard_door=gate)}
        self.assertTrue(game.blocked_door(gate))
        game.interact()
        self.assertEqual(run.area, building)
        run.position = game.rooms[building].entry
        game.interact()
        self.assertEqual(run.area, "campus")

    def test_side_entrances_connect_to_distinct_walkable_interiors(self):
        game = self.game
        for area, point in game.slots.side_entries.items():
            with self.subTest(area=area):
                room = game.rooms[area]
                outside = game.slots.side_exits[area]
                self.assertNotEqual(room.entry, point)
                self.assertFalse(room.hit(body(point)))
                self.assertTrue(walkable_steps(room.entry, point, room.hit))
                self.assertFalse(game.world.collides(body(outside)))
                self.assertLess(min(pygame.Vector2(outside).distance_to(cell)
                                    for cell in game.slots.reachable), 20)

    def test_thrower_telegraphs_and_takes_aim_before_projectile_flight(self):
        run = Run(3, (160, 100), area="gym")
        enemy = Actor("thrower", (20, 100), "gym", "hostile")
        run.actors["thrower"] = enemy
        notices = simulate(run, .05, pygame.Vector2(), False, lambda _: False)
        self.assertIn("throw_warning", notices)
        self.assertEqual(enemy.throw_target, (160, 100))
        self.assertFalse(run.projectiles)
        run.position = (160, 135)
        simulate(run, .8, pygame.Vector2(), False, lambda _: False)
        self.assertEqual(len(run.projectiles), 1)
        self.assertEqual(run.projectiles[0].velocity, (350, 0))
        for _ in range(40):
            simulate(run, .03, pygame.Vector2(), False, lambda _: False)
        self.assertEqual(run.injury_until, 0)

    def test_old_save_removes_light_items_and_converts_old_infected(self):
        from dataclasses import asdict
        payload = asdict(self.game.run_state)
        payload["pack"] = {"food": 1, "water": 0, "bat": 1, "lamp": 1, "cell": 3, "bike": 1}
        payload["selected"] = 5
        payload["battery"], payload["lamp_on"] = 63, True
        payload["access_ready"] = False
        payload["actors"]["enemy_0"]["kind"] = "wanderer"
        payload["actors"]["enemy_0"]["health"] = 2
        old = Run.read(payload)
        self.game.slots.restore_access(old)
        self.assertEqual(old.actors["enemy_0"].kind, "hunter")
        self.assertEqual(tuple(old.pack), GEAR)
        self.assertEqual(GEAR[old.selected], "bike")
        self.assertTrue(any(cache.item == "key" and cache.area not in old.locked for cache in old.caches))

    def test_save_roundtrip_and_corrupt_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            run = self.game.run_state
            run.area = "education"
            run.observe("evacuation")
            run.position = self.game.rooms["education"].entry
            run.caches[0].taken = True
            run.add_gear("food")
            store.save(run)
            loaded = store.load()
            self.assertEqual(loaded.seed, run.seed)
            self.assertEqual(loaded.area, "education")
            self.assertEqual(loaded.observations, ["evacuation"])
            self.assertTrue(loaded.caches[0].taken)
            self.assertEqual(loaded.pack, run.pack)
            (Path(directory) / "run.json").write_text("partial", encoding="utf-8")
            self.assertIsNone(store.load())
            self.assertEqual(len(list(Path(directory).glob("run.corrupt-*.json"))), 1)

    def test_resume_relocates_old_position_inside_restored_guest_house(self):
        g = self.game
        old_position = pygame.Rect(CAMPUS_BUILDINGS["faculty_housing"]["rect"].pixels()).center
        g.run_state.position = old_position
        g.run_state.trail = [old_position]
        g.run_state.observe("evacuation")
        g.store.save(g.run_state)
        g.resume_run = g.store.load()
        g.resume()
        self.assertFalse(g.world.collides(body(g.run_state.position)))
        self.assertLess(pygame.Vector2(old_position).distance_to(g.run_state.position), 130)
        self.assertFalse(g.run_state.trail)
        self.assertIn("evacuation", g.run_state.observations)

    def test_chinese_composition_enter_and_profile_save(self):
        g = self.game
        g.profile.name = "林"
        g.scene = "title"
        g.action("customize")
        g.action("confirm")
        self.assertTrue(g.name_focused)

        g.event(pygame.event.Event(pygame.TEXTEDITING, text="ㄑㄧㄥ", start=3, length=0), (0, 0))
        g.key(pygame.K_BACKSPACE)
        g.key(pygame.K_RETURN)
        self.assertEqual(g.scene, "profile")
        self.assertEqual(g.profile.name, "林")
        self.assertEqual(g.name_composition, "ㄑㄧㄥ")
        g.draw((0, 0))

        # The native Windows backend can queue an empty preedit and commit before Enter.
        g.event(pygame.event.Event(pygame.TEXTEDITING, text="", start=0, length=0), (0, 0))
        g.event(pygame.event.Event(pygame.TEXTINPUT, text="清華"), (0, 0))
        g.key(pygame.K_RETURN)
        self.assertEqual(g.profile.name, "林清華")
        self.assertEqual(g.scene, "profile")
        g.key(pygame.K_TAB)
        g.key(pygame.K_RETURN)
        self.assertEqual(g.scene, "intro")
        self.assertFalse(g.name_focused)
        self.assertEqual(g.store.profile().name, "林清華")

    def test_name_field_focus_paste_and_character_limit(self):
        g = self.game
        g.profile.name = ""
        self.addCleanup(setattr, g.profile, "name", "")
        g.action("confirm")
        g.key(pygame.K_TAB)
        g.event(pygame.event.Event(pygame.TEXTINPUT, text="略過"), (0, 0))
        self.assertEqual(g.profile.name, "")
        g.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1), (600, 260))
        self.assertTrue(g.name_focused)
        with patch("pygame.scrap.get_text", return_value="清華大學\n甲乙丙丁戊己庚辛壬"):
            g.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, mod=pygame.KMOD_CTRL), (0, 0))
        self.assertEqual(g.profile.name, "清華大學甲乙丙丁戊己庚辛")
        g.key(pygame.K_BACKSPACE)
        g.event(pygame.event.Event(pygame.TEXTINPUT, text="Z"), (0, 0))
        self.assertEqual(g.profile.name, "清華大學甲乙丙丁戊己庚Z")
        g.action("cancel_profile")
        self.assertFalse(g.name_focused)

    def test_outdoor_facades_have_localized_nameplates(self):
        g = self.game
        for language in ("zh_TW", "en"):
            g.localizer.set_language(language)
            for key in ("main_library", "education", "general_4", "ren_hall", "faculty_housing"):
                with self.subTest(language=language, building=key):
                    g.run_state.position = g.building_entrances[key]
                    with patch.object(g, "words", wraps=g.words) as render:
                        g.draw((0, 0))
                    self.assertIn(g.campus_name(key), [call.args[0] for call in render.call_args_list])

    def test_map_lists_every_building_and_selects_its_pin(self):
        g = self.game
        g.key(pygame.K_m)
        g.map_zoom = False
        for language in ("zh_TW", "en"):
            g.localizer.set_language(language)
            g.map_page = 0
            listed = set()
            for _ in range((len(g.map_points) + MAP_PAGE_SIZE - 1) // MAP_PAGE_SIZE):
                with patch.object(g, "button", wraps=g.button) as button:
                    g.draw((0, 0))
                for call in button.call_args_list:
                    title, action = call.args[1:3]
                    if action.startswith("map_pin/"):
                        key = action.split("/", 1)[1]
                        self.assertEqual(title, g.campus_name(key))
                        self.assertFalse(title.startswith("["))
                        listed.add(key)
                g.key(pygame.K_PAGEDOWN)
            self.assertTrue(CAMPUS_BUILDINGS.keys() <= listed)
        _, bounds, rect, scale = g.map_layer()
        pins = g.map_pin_positions(bounds, rect, scale)
        g.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1), pins["faculty_housing"])
        self.assertEqual(g.map_selected, "faculty_housing")
        self.assertEqual(g.map_page, list(pins).index("faculty_housing") // MAP_PAGE_SIZE)
        g.action("zoom")
        self.assertEqual(g.map_page, 0)
        self.assertEqual(g.scene, "map")
        g.action("zoom")
        g.map_selected = None

    def test_night_keeps_nearby_vision_without_removed_gear(self):
        game = self.game
        run = game.run_state
        run.position = game.building_entrances["main_library"]
        run.observe("playback")
        camera = game.world.camera_for(*run.position)
        origin = pygame.Vector2(run.position) - camera.topleft
        with patch("pygame.time.get_ticks", return_value=1200):
            game.draw_play((0, 0), hud=True)
        self.assertNotEqual(game.canvas.get_at(origin + (25, 0))[:3], (0, 0, 0))
        self.assertTrue(game.lit_at(pygame.Vector2(run.position) + (125, 0)))
        self.assertFalse(game.lit_at(pygame.Vector2(run.position) + (180, 0)))
        self.assertNotIn("lamp", run.pack)
        self.assertNotIn("cell", run.pack)

    def test_title_rain_moves_and_waiting_indoor_npc_stays_still(self):
        game = self.game
        game.scene = "title"
        with patch("pygame.time.get_ticks", return_value=100):
            game.draw((0, 0))
        first = game.canvas.copy()
        with patch("pygame.time.get_ticks", return_value=400):
            game.draw((0, 0))
        self.assertNotEqual(pygame.image.tobytes(first, "RGB"), pygame.image.tobytes(game.canvas, "RGB"))
        game.scene = "play"
        state = game.run_state
        state.area = "education"
        state.position = game.rooms[state.area].entry
        state.actors["student"].moving = True
        with patch("pygame.time.get_ticks", return_value=150):
            game.draw_play((0, 0), False)
        first = game.canvas.copy()
        with patch("pygame.time.get_ticks", return_value=460):
            game.draw_play((0, 0), False)
        self.assertEqual(pygame.image.tobytes(first, "RGB"), pygame.image.tobytes(game.canvas, "RGB"))

    def test_audio_stays_active_across_transitions_and_recovers_dropped_loop(self):
        game = self.game
        game.profile.sound = True
        game.scene = "title"
        game.update_audio(.3)
        self.assertGreater(game.audio.levels["dusk"], 0)
        game.run_state.blackout = True
        game.scene = "incident"
        game.update_audio(.05)
        self.assertGreater(game.audio.levels["dusk"], 0)
        self.assertGreater(game.audio.levels["night"], 0)
        game.audio.channels["night"].stop()
        game.update_audio(.05)
        self.assertTrue(game.audio.channels["night"].get_busy())
        game.scene = "ending"
        game.update_audio(.05)
        self.assertGreater(game.audio.levels["arrival"], 0)
        self.assertFalse(hasattr(game.audio, "speak"))

    def test_character_options_and_late_distinct_mutations(self):
        game = self.game
        game.action("style/gender/0")
        male = game.world.characters.sprite("down", 0, game.profile.appearance)
        game.action("style/gender/1")
        female = game.world.characters.sprite("down", 0, game.profile.appearance)
        self.assertNotEqual(pygame.image.tobytes(male, "RGBA"), pygame.image.tobytes(female, "RGBA"))
        game.settings_save()
        self.assertEqual(game.store.profile().appearance["gender"], 1)
        run = game.run_state
        variants = [actor for key, actor in run.actors.items() if key.startswith("mutation_")]
        self.assertEqual({actor.kind for actor in variants}, set(MUTATIONS))
        self.assertTrue(all(actor.status == "dormant" for actor in variants))
        run.start_outbreak()
        run.elapsed += 25
        run.release_infected()
        self.assertTrue(all(actor.status == "dormant" for actor in variants))
        run.elapsed += 60
        run.release_infected()
        self.assertTrue(all(actor.status == "hostile" for actor in variants))
        art = game.world.characters
        self.assertLess(art.zombie_sprite("hidden", "down", 0, False).get_height(),
                        art.zombie_sprite("thrower", "down", 0, False).get_height())

    def test_supply_interaction_reveals_contents_only_once(self):
        game = self.game
        state = game.run_state
        cache = next(cache for cache in state.caches if cache.item == "water")
        self.assertFalse(any(kind == "cache" and key == cache.id for kind, key, _ in game.interactions()))
        state.area, state.position = cache.area, cache.position
        self.assertIn(cache.container, ("drawer", "shelf", "cabinet"))
        self.assertEqual(state.pack["water"], 0)
        game.interact()
        self.assertEqual(state.pack["water"], 1)
        game.interact()
        self.assertEqual(state.pack["water"], 1)
        self.assertTrue(cache.taken)

    def test_pursuers_use_the_same_door_with_a_grace_period(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        building = "education"
        run.add_gear("key")
        door = game.slots.doors[building]
        run.position = door
        start = next(point for point in game.slots.reachable
                     if 55 < pygame.Vector2(door).distance_to(point) < 95
                     and not game.world.collides(body(point)))
        # Put the pursuer at the threshold to make line-of-sight deterministic.
        chasing = Actor("hunter", tuple(door), status="hostile", target="player", chasing=True)
        waiting = Actor("hunter", start, status="hostile")
        run.actors = {"first": chasing, "second": waiting}
        game.profile.scares = True
        game.interact()
        self.assertEqual(run.area, building)
        self.assertEqual(chasing.area, building)
        self.assertEqual(waiting.area, "campus")
        self.assertGreater(chasing.entry_delay, 1)
        self.assertFalse(game.rooms[building].hit(body(chasing.position)))
        for _ in range(28):
            game.update(.05)
        self.assertIsNone(run.death)
        self.assertEqual(chasing.entry_delay, 0)
        self.assertGreater(game.scare_time, 0)
        game.draw((0, 0))
        game.action("scares")
        self.assertEqual(game.scare_time, 0)
        game.profile.scares = True

    def test_latched_door_excludes_pursuer_and_is_saved(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        building = "education"
        run.add_gear("key")
        door = game.slots.doors[building]
        run.position = door
        run.latched[building] = run.elapsed + 20
        enemy = Actor("hunter", tuple(door), status="hostile", target="player", chasing=True)
        run.actors = {"first": enemy}
        game.interact()
        self.assertEqual(run.area, building)
        self.assertEqual(enemy.area, "campus")
        self.assertEqual(game.store.load().latched, run.latched)

    def test_run_catalogs_match(self):
        catalogs = self.game.localizer.catalogs
        keys = [{key for key in catalog if key.startswith("survival.")} for catalog in catalogs.values()]
        self.assertEqual(*keys)
        self.assertGreater(len(keys[0]), 100)


if __name__ == "__main__":
    unittest.main()
