import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

from nthu_adventure.expedition import (
    DARK_MINUTE, DECISIONS, ENEMY_SPEED, EVENTS, EXTRA_CLUES, MAIN_STEPS, MAX_OUTDOOR_EVENTS, MAX_ROUTE_STOPS,
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
        self.assertEqual(seen, DECISIONS["events"].keys())
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
        self.assertEqual(sum(key.startswith("enemy_") and actor.status == "hostile" for key, actor in r.actors.items()), 30)

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
        r.elapsed = (DARK_MINUTE + 10 - START_MINUTE) * MINUTE_SECONDS
        self.assertEqual(len(g.rooms), 20)
        r.add_gear("key")
        for key, room in g.rooms.items():
            with self.subTest(building=key):
                r.position = g.slots.doors[key]
                g.key(pygame.K_e)
                self.assertEqual(r.area, key)
                r.position = room.event_point
                self.assertFalse(room.hit(body(r.position)))
                g.key(pygame.K_e)
                self.assertEqual(g.scene, "card")
                self.assertGreaterEqual(len(g.options), 2)
                self.assertEqual(r.encounters[key].status, "heard")
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

    def test_hidden_infected_reveals_before_chasing_in_both_areas(self):
        for area in ("campus", "dining_hall"):
            run = Run(2, (100, 100), area=area)
            infected = Actor("hidden", (150, 100), area, "hostile", concealed=True)
            run.actors["test"] = infected
            notices = simulate(run, .05, pygame.Vector2(), False, lambda _: False)
            self.assertIn("hidden_reveal", notices)
            self.assertFalse(infected.concealed)
            self.assertEqual(infected.position, (150, 100))
            self.assertGreater(infected.reveal, 0)
            simulate(run, .75, pygame.Vector2(), False, lambda _: False)
            simulate(run, .1, pygame.Vector2(), False, lambda _: False)
            self.assertTrue(infected.chasing)

    def test_locked_main_and_side_doors_share_key_and_separate_destinations(self):
        game = self.game
        run = game.run_state
        run.locked = ["gym"]
        run.position = game.slots.side_exits["gym"]
        game.interact()
        self.assertEqual(run.area, "campus")
        run.add_gear("key")
        game.interact()
        self.assertEqual(run.area, "gym")
        self.assertEqual(run.position, game.slots.side_entries["gym"])
        self.assertNotEqual(run.position, game.rooms["gym"].entry)
        self.assertNotIn("gym", run.locked)
        game.interact()
        self.assertEqual(run.area, "campus")
        self.assertEqual(run.position, game.slots.side_exits["gym"])
        self.assertEqual(run.pack["key"], 1)

    def test_agile_chase_and_stalker_holds_back(self):
        run = Run(1, (100, 100))
        actor = Actor("hunter", (185, 100), status="hostile")
        run.actors["test"] = actor
        simulate(run, .1, pygame.Vector2(), False, lambda _: False)
        self.assertAlmostEqual(actor.position[0], 185 - 110 * 1.33 * ENEMY_SPEED * .1, places=2)
        actor.kind = "stalker"
        actor.position = (196, 100)
        simulate(run, .1, pygame.Vector2(), False, lambda _: False)
        self.assertEqual(actor.position, (196, 100))

    def test_every_random_encounter_stays_hidden_until_outbreak(self):
        g = self.game
        r = g.run_state
        r.elapsed = (STOP_MINUTE - START_MINUTE) * MINUTE_SECONDS
        g.advance_crisis()
        self.assertFalse(r.outbreak)
        self.assertFalse(any(event.available(r) for event in r.encounters.values()))
        r.add_gear("key")
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
        r.elapsed = (DARK_MINUTE + 10 - START_MINUTE) * MINUTE_SECONDS
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

    def test_new_events_have_distinct_time_windows(self):
        run = Run(1, (0, 0))
        early = Encounter("lawn_split", "worker", 0)
        later = Encounter("hidden_bite", "resident", 1)
        self.assertFalse(early.available(run))
        run.start_outbreak()
        self.assertTrue(early.available(run))
        self.assertFalse(later.available(run))
        run.elapsed = (18*60 + 13 - START_MINUTE)*MINUTE_SECONDS
        self.assertFalse(early.available(run))
        self.assertTrue(later.available(run))

    def test_plaza_trade_requires_a_resource_and_gives_the_selected_return(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        point = game.encounters.outdoors["plaza_exchange"]
        run.position = point
        event = Encounter("plaza_exchange", "worker", 0)
        run.encounters = {"plaza_exchange": event}
        game.interact()
        game.resolve("event_1/plaza_exchange")
        self.assertEqual(run.pack["food"], 0)
        self.assertNotEqual(event.status, "resolved")
        run.add_gear("water")
        game.resolve("event_1/plaza_exchange")
        self.assertEqual(run.pack["water"], 0)
        self.assertEqual(run.pack["food"], 1)
        self.assertEqual(event.outcome, "exchange_food")

    def test_all_outdoor_events_accept_interaction_and_translate(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        run.elapsed = (DARK_MINUTE + 10 - START_MINUTE) * MINUTE_SECONDS
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
                self.assertGreaterEqual(len(game.options), 2)
                for lang in ("zh_TW", "en"):
                    game.localizer.set_language(lang)
                    self.assertNotIn("[survival.", game.tr(game.card[0]))
                    self.assertNotIn("[survival.", game.tr(game.card[1]))
                    labels = [game.encounters.option_label(action) for action in game.options]
                    self.assertEqual(len(set(labels)), len(labels))
                    self.assertTrue(all("[survival." not in label for label in labels))
                game.key(pygame.K_ESCAPE)

    def test_parcel_choice_creates_work_and_pays_only_after_delivery(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        run.area = "general_4"
        run.position = game.rooms[run.area].event_point
        event = Encounter("parcel_shift", "worker", 0)
        run.encounters = {run.area: event}
        game.interact()
        game.resolve("event_2/general_4")
        self.assertEqual(event.outcome, "task_parcel")
        self.assertEqual(run.pack["food"], 0)
        self.assertTrue(run.event_progress["carrying_parcel"])
        self.assertTrue(game.card_event)
        game.key(pygame.K_m)
        self.assertEqual(game.scene, "map")
        self.assertEqual(run.event_progress["mission"]["area"], "general_4")
        game.key(pygame.K_m)
        self.assertEqual(game.scene, "card")
        game.key(pygame.K_ESCAPE)
        game.key(pygame.K_g)
        self.assertNotIn("carrying_parcel", run.event_progress)
        game.interact()
        self.assertTrue(run.event_progress["carrying_parcel"])
        run.position = run.event_progress["mission"]["point"]
        game.interact()
        self.assertNotIn("mission", run.event_progress)
        self.assertEqual(run.pack["food"], 1)
        self.assertEqual(event.outcome, "parcel_delivered")

    def test_bad_list_sends_player_to_wrong_site_then_updates_marker(self):
        game = self.game
        run = game.run_state
        run.start_outbreak()
        run.elapsed = (18*60 - START_MINUTE)*MINUTE_SECONDS
        run.area = "main_library"
        run.position = game.rooms[run.area].event_point
        event = Encounter("evacuation_list", "worker", 0)
        run.encounters = {run.area: event}
        game.interact()
        game.resolve("event_2/main_library")
        self.assertEqual(event.outcome, "task_wrong_list")
        _, position = game.encounters.waypoint()
        run.area, run.position = "campus", position
        game.key(pygame.K_ESCAPE)
        game.interact()
        self.assertEqual(event.outcome, "list_wrong")
        _, position = game.encounters.waypoint()
        run.position = position
        game.interact()
        self.assertEqual(event.outcome, "list_confirmed")
        self.assertNotIn("mission", run.event_progress)

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
