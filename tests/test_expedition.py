import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

from nthu_adventure.expedition import (
    DARK_MINUTE, ENEMY_SPEED, EVENTS, EXTRA_CLUES, MAIN_STEPS, MAX_OUTDOOR_EVENTS, MAX_ROUTE_STOPS,
    MIN_OUTDOOR_EVENTS, MIN_ROUTE_STOPS, MINUTE_SECONDS, OUTBREAK_SITES, OUTDOOR_CLUES,
    OUTDOOR_POINTS, ROOM_EVENTS, SIGNAL_MINUTE, START_MINUTE, STOP_MINUTE,
    Encounter, choose_events, main_route, outbreak_site, valid_route,
)
from nthu_adventure.survival import Run, body, nearby_targets, simulate, Actor
from nthu_adventure.survival_game import Game


class ExpeditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.game = Game(Path(cls.temp.name))
        cls.addClassCleanup(cls.temp.cleanup)
        cls.addClassCleanup(pygame.quit)
        cls.addClassCleanup(cls.game.audio.close)

    def setUp(self):
        self.game.begin(103)
        self.game.finish_intro()

    def test_seeded_events_use_every_variant_and_compatible_distinct_people(self):
        seen, casts, counts = set(), set(), set()
        for seed in range(100):
            plan = choose_events(seed)
            seen.update(event.event for event in plan.values())
            casts.add(tuple(event.person for event in plan.values()))
            self.assertEqual(len(set(event.person for event in plan.values())), len(plan))
            outdoors = sum(key in OUTDOOR_POINTS for key in plan)
            counts.add(outdoors)
            self.assertEqual(len(plan), len(ROOM_EVENTS) + outdoors)
            for event in plan.values():
                self.assertIn(event.role, EVENTS[event.event]["roles"])
        self.assertEqual(seen, EVENTS.keys())
        self.assertEqual(len(casts), 100)
        self.assertEqual(counts, set(range(MIN_OUTDOOR_EVENTS, MAX_OUTDOOR_EVENTS + 1)))
        self.assertEqual(choose_events(41), choose_events(41))

    def test_clock_blackout_and_two_outbreak_triggers(self):
        g = self.game
        r = g.run_state
        self.assertEqual(r.clock, "17:42")
        self.assertTrue(any(a.status == "passing" for _, a in nearby_targets(r, "campus")))
        self.assertFalse(any(a.infected for _, a in nearby_targets(r, "campus")))
        r.elapsed = (STOP_MINUTE - START_MINUTE) * MINUTE_SECONDS
        g.advance_crisis()
        self.assertTrue(r.blackout)
        self.assertFalse(r.outbreak)
        self.assertEqual(r.clock, "17:45")
        self.assertTrue(r.night)
        r.position = g.slots.incidents[r.incident_site]
        g.advance_crisis()
        self.assertTrue(r.outbreak)
        self.assertEqual(g.scene, "incident")
        g.draw((0, 0))
        g.update(6)
        self.assertEqual(g.scene, "play")
        wave_one = sum(a.status == "hostile" for a in r.actors.values())
        self.assertGreater(wave_one, 0)
        self.assertLess(wave_one, 30)
        r.elapsed += 21
        r.release_infected()
        self.assertEqual(sum(a.status == "hostile" for a in r.actors.values()), 30)

        g.begin(202)
        g.finish_intro()
        r = g.run_state
        r.elapsed = (SIGNAL_MINUTE - START_MINUTE) * MINUTE_SECONDS
        g.advance_crisis()
        self.assertEqual(g.scene, "play")
        self.assertTrue(r.outbreak)
        r.elapsed = (DARK_MINUTE - START_MINUTE) * MINUTE_SECONDS
        self.assertTrue(r.night)
        g.scene = "map"
        g.update(18)
        self.assertEqual(r.clock, "18:00")

    def test_all_twenty_interiors_open_and_their_encounters_accept_input(self):
        g = self.game
        r = g.run_state
        r.start_outbreak()
        r.elapsed = (DARK_MINUTE + 5 - START_MINUTE) * MINUTE_SECONDS
        self.assertEqual(len(g.rooms), 20)
        for key, room in g.rooms.items():
            with self.subTest(building=key):
                r.position = g.slots.doors[key]
                g.key(pygame.K_e)
                self.assertEqual(r.area, key)
                r.position = room.event_point
                self.assertFalse(room.hit(body(r.position)))
                g.key(pygame.K_e)
                self.assertEqual(g.scene, "card")
                self.assertIn("event_check/"+key, g.options)
                g.key(pygame.K_1)
                self.assertEqual(r.encounters[key].status, "checked")
                self.assertNotIn("[survival.", g.card_quote)
                g.draw((0, 0))
                g.key(pygame.K_ESCAPE)
                r.position = room.entry
                g.key(pygame.K_e)
                self.assertEqual(r.area, "campus")
        g.key(pygame.K_q)
        g.action("event_log")
        self.assertEqual(g.scene, "event_log")
        g.draw((0, 0))
        g.action("event_next")
        g.draw((0, 0))
        self.assertEqual(g.event_page, 1)
        restored = g.store.load()
        self.assertEqual(restored.encounters, r.encounters)
        self.assertEqual(restored.clock, r.clock)
        self.assertTrue(restored.outbreak)

    def test_mimic_uses_prior_voice_and_reveals_itself_only_on_approach(self):
        g = self.game
        seed = next(seed for seed in range(200) if choose_events(seed)["dining_hall"].role == "mimic")
        g.begin(seed)
        g.finish_intro()
        r = g.run_state
        r.start_outbreak()
        r.heard_event, r.heard_voice = "cooperate.1", "male"
        r.position = g.slots.doors["dining_hall"]
        g.interact()
        r.position = g.rooms["dining_hall"].event_point
        g.interact()
        self.assertEqual(g.card_quote, g.tr("exp.voice.cooperate.1"))
        self.assertFalse(hasattr(g.audio, "speak"))
        encounter = r.encounters["dining_hall"]
        actor = r.actors[encounter.actor_id]
        self.assertFalse(actor.infected)
        g.resolve("event_check/dining_hall")
        self.assertFalse(actor.infected)
        g.resolve("event_approach/dining_hall")
        self.assertTrue(actor.infected)
        self.assertEqual(encounter.outcome, "lure")
        self.assertGreater(actor.cooldown, 1)

    def test_indoor_route_unlock_and_real_open_exit(self):
        g = self.game
        seed = next(seed for seed in range(50) if choose_events(seed)["gym"].event == "court_crossing")
        g.begin(seed)
        g.finish_intro()
        r = g.run_state
        r.start_outbreak()
        r.position = g.slots.doors["gym"]
        g.interact()
        room = g.rooms["gym"]
        r.position = room.event_point
        g.interact()
        g.resolve("event_take_route/gym")
        self.assertIn("gym", r.shortcuts)
        g.key(pygame.K_RETURN)
        r.position = next(f.point for f in room.fixtures if f.key == "side_exit")
        g.key(pygame.K_e)
        self.assertEqual(r.area, "campus")
        self.assertEqual(r.position, g.slots.side_exits["gym"])
        self.assertFalse(g.world.collides(body(r.position)))

    def test_applying_slowdown_to_live_chase_and_mimic_waiting(self):
        r = Run(1,(100,100))
        actor = Actor("wanderer",(185,100),status="hostile")
        r.actors["test"] = actor
        simulate(r, .1, pygame.Vector2(), False, lambda _: False)
        self.assertAlmostEqual(actor.position[0], 185 - 66 * ENEMY_SPEED * .1, places=2)
        actor.kind, actor.chasing = "mimic", True
        actor.linger = 6
        prev = actor.position
        r.position = (350,100)
        notices = simulate(r, .1, pygame.Vector2(), False, lambda _: False)
        self.assertEqual(actor.position, prev)
        self.assertIn("mimic_wait", notices)

    def test_every_random_encounter_stays_hidden_until_outbreak(self):
        g = self.game
        r = g.run_state
        r.elapsed = (STOP_MINUTE - START_MINUTE) * MINUTE_SECONDS
        g.advance_crisis()
        self.assertFalse(r.outbreak)
        self.assertFalse(any(event.available(r) for event in r.encounters.values()))
        r.position = g.slots.doors["gym"]
        g.interact()
        g.encounters.sync()
        self.assertEqual(r.area, "gym")
        self.assertFalse(any(item[0] == "encounter" for item in g.interactions()))
        self.assertFalse(any(key.startswith("enc_") for key in r.actors))
        r.position = g.rooms["gym"].story_point
        g.read_story(r.goal)
        self.assertNotIn(r.goal, r.observations)
        r.start_outbreak()
        r.elapsed = (DARK_MINUTE + 5 - START_MINUTE) * MINUTE_SECONDS
        self.assertTrue(r.encounters["gym"].available(r))
        g.encounters.sync()
        self.assertTrue(any(item[0] == "encounter" for item in g.interactions()))

    def test_story_routes_reach_all_rooms_and_persist_without_reshuffle(self):
        g = self.game
        seen_places, seen_clues, counts, sites = set(), set(), set(), set()
        for seed in range(250):
            route = main_route(seed)
            self.assertTrue(valid_route(route))
            self.assertEqual(len(set(route.values())), len(route))
            self.assertIn(route["sealed"], ROOM_EVENTS)
            self.assertTrue(set(route.values()) & OUTDOOR_CLUES.keys())
            seen_places.update(route.values())
            seen_clues.update(route)
            counts.add(len(route))
            sites.add(outbreak_site(seed))
        self.assertEqual(seen_places, ROOM_EVENTS.keys() | OUTDOOR_CLUES.keys())
        self.assertEqual(seen_clues, set(MAIN_STEPS + EXTRA_CLUES))
        self.assertEqual(counts, set(range(MIN_ROUTE_STOPS, MAX_ROUTE_STOPS + 1)))
        self.assertEqual(sites, set(OUTBREAK_SITES))
        r = g.run_state
        r.start_outbreak()
        for clue in tuple(r.route)[:3]:
            r.observe(clue)
        g.store.save(r)
        saved = g.store.load()
        self.assertEqual(saved.route, r.route)
        self.assertEqual(saved.incident_site, r.incident_site)
        self.assertEqual(saved.goal, tuple(r.route)[3])
        self.assertEqual(tuple(saved.route), tuple(r.route))

    def test_expanding_old_roster_keeps_resolved_events_and_outdoor_choices(self):
        from dataclasses import asdict
        g = self.game
        payload = asdict(g.run_state)
        added_rooms = ("admin_hall", "engineering_2", "computer_science", "student_center", "humanities_building")
        for key in added_rooms:
            payload["encounters"].pop(key)
        payload["encounters"]["education"].update(status="resolved", clock=1100, outcome="information")
        old = payload["encounters"].copy()
        payload.pop("route")
        payload.pop("incident_site")
        loaded = Run.read(payload)
        self.assertEqual(len(loaded.encounters), len(choose_events(loaded.seed)))
        self.assertEqual(len(set(event.person for event in loaded.encounters.values())), len(loaded.encounters))
        self.assertEqual({key: asdict(loaded.encounters[key]) for key in old}, old)
        self.assertEqual(loaded.encounters["education"].outcome, "information")
        self.assertEqual(loaded.route, main_route(loaded.seed))

    def test_four_stop_save_retains_its_progress_while_gaining_events(self):
        from dataclasses import asdict

        payload = asdict(self.game.run_state)
        route = dict(zip(MAIN_STEPS, tuple(ROOM_EVENTS)[:4], strict=True))
        payload["route"] = route
        payload["observations"] = ["manifest", "echo_log"]
        outdoor = [key for key in payload["encounters"] if key in OUTDOOR_POINTS]
        for key in outdoor[4:]:
            payload["encounters"].pop(key)
        old = payload["encounters"].copy()
        loaded = Run.read(payload)
        self.assertEqual(loaded.route, route)
        self.assertEqual(loaded.goal, "lock_log")
        self.assertGreater(len(loaded.encounters), len(old))
        self.assertEqual({key: asdict(loaded.encounters[key]) for key in old}, old)

    def test_new_outdoor_events_activate_on_seeded_delays(self):
        key = "clock_radio"
        delays = set()
        for seed in range(25):
            run = Run(seed, (0, 0), elapsed=(SIGNAL_MINUTE - START_MINUTE) * MINUTE_SECONDS)
            event = Encounter(key, "guard", 0)
            delay = event.delay(seed)
            delays.add(delay)
            self.assertFalse(event.available(run))
            run.start_outbreak()
            if delay:
                run.elapsed += delay * MINUTE_SECONDS - 1
                self.assertFalse(event.available(run))
                run.elapsed += 1
            self.assertTrue(event.available(run))
        self.assertEqual(delays, set(range(6)))

    def test_warning_verification_changes_resources_and_infected_attention(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        point = game.encounters.outdoors["clock_radio"]
        run.position = point
        person = Actor("guard", point)
        enemy = Actor("hunter", (point[0] + 30, point[1]), status="hostile")
        run.actors = {"test": enemy}
        event = Encounter("clock_radio", "guard", 0)
        self.assertEqual(game.encounters.apply("warn", "clock_radio", event, person), "warning_loud")
        self.assertEqual(enemy.alerted, 6)
        self.assertEqual(run.pack["water"], 0)
        enemy.alerted = 0
        event.status = "checked"
        self.assertEqual(game.encounters.apply("warn", "clock_radio", event, person), "warning_quiet")
        self.assertEqual(enemy.alerted, 0)
        self.assertEqual(run.pack["water"], 1)

    def test_all_outdoor_events_accept_interaction_and_translate(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        run.elapsed = (DARK_MINUTE + 5 - START_MINUTE) * MINUTE_SECONDS
        for key, point in game.encounters.outdoors.items():
            with self.subTest(event=key):
                self.assertFalse(game.world.collides(body(point)))
                self.assertLess(min(pygame.Vector2(point).distance_to(cell) for cell in game.slots.reachable), 20)
                event = Encounter(key, EVENTS[key]["roles"][0], 0)
                run.encounters = {key: event}
                run.position = point
                self.assertTrue(event.available(run), key)
                game.interact()
                self.assertEqual(game.scene, "card")
                self.assertIn("event_check/" + key, game.options)
                for lang in ("zh_TW", "en"):
                    game.localizer.set_language(lang)
                    self.assertNotIn("[survival.", game.tr(game.card[0]))
                    self.assertNotIn("[survival.", game.tr(game.card[1]))
                game.key(pygame.K_ESCAPE)

    def test_new_events_have_different_consequences(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        run.area = "admin_hall"
        person = Actor("aide", game.rooms[run.area].event_point, run.area)
        latch = Encounter("service_latch", "aide", 0, status="checked")
        self.assertEqual(game.encounters.apply("barricade", run.area, latch, person), "barred")
        self.assertGreaterEqual(run.latched[run.area] - run.elapsed, 45)
        radio = Encounter("parts_radio", "worker", 1, status="checked")
        self.assertEqual(game.encounters.apply("divert", run.area, radio, person), "divert")
        self.assertEqual(run.lure_point, person.position)
        self.assertGreater(run.lure_until, run.elapsed)
        kit = Encounter("folded_kit", "worker", 1)
        self.assertEqual(game.encounters.apply("water", run.area, kit, person), "kit_water")
        self.assertEqual(run.pack["water"], 1)
        self.assertEqual(run.pack["food"], 0)

    def test_escort_earns_water_only_after_going_outside(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        run.area = "gym"
        run.position = game.rooms["gym"].entry
        event = Encounter("injured_runner", "stranded", 1, status="heard", clock=1100)
        run.encounters["gym"] = event
        person = Actor("stranded", run.position, "gym")
        run.actors[event.actor_id] = person
        game.encounters.resolve("escort", "gym")
        self.assertIn(event.actor_id, run.team)
        self.assertEqual(run.pack["water"], 0)
        game.key(pygame.K_ESCAPE)
        game.key(pygame.K_e)
        self.assertEqual(run.area, "campus")
        self.assertEqual(event.outcome, "escort_complete")
        self.assertEqual(person.status, "gone")
        self.assertEqual(run.pack["water"], 1)

    def test_old_save_initializes_seeded_roster_and_hides_early_enemies(self):
        g = self.game
        from dataclasses import asdict
        old = asdict(g.run_state)
        for key in ("encounters","outbreak","outbreak_at","blackout","storm_until","shortcuts","heard_event","heard_voice"):
            old.pop(key)
        old["actors"]["enemy_0"]["status"] = "hostile"
        loaded = Run.read(old)
        self.assertEqual(len(loaded.encounters), len(choose_events(loaded.seed)))
        self.assertEqual(loaded.actors["enemy_0"].status, "dormant")
        self.assertFalse(loaded.outbreak)


if __name__ == "__main__":
    unittest.main()
