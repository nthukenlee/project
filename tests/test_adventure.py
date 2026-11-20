from collections import deque
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from nthu_adventure.adventure import ENDING_ID, INTRO_DURATION, SIDE_STOPS, STOPS
from nthu_adventure.app import Game
from nthu_adventure.constants import MAP_COLS, MAP_ROWS, TILE
from nthu_adventure.content import SPAWN_TILE, tile_center
from nthu_adventure.state import GameState
from nthu_adventure.zombie_story import body_at


class CampusAdventureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.game = Game(Path(cls.directory.name))
        cls.addClassCleanup(pygame.quit)

    def setUp(self):
        self.game._set_state(GameState())
        self.game.scene = 'title'

    def key(self, key):
        self.game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), (0, 0))

    def outdoor(self, stop):
        self.game.state.player_x, self.game.state.player_y = stop.position(self.game.world)
        self.game.scene = 'explore'
        self.key(pygame.K_e)

    def interior(self, stop):
        self.outdoor(stop)
        self.assertEqual(self.game.scene, 'interior')
        self.assertEqual(self.game.current_interior['id'], stop.building)
        x, y = dict(self.game._room_objects())[stop.fixture]
        self.game.room_position = pygame.Vector2(max(.35, min(.65, x)), max(.30, y))
        self.key(pygame.K_e)
        self.assertEqual(self.game.scene, 'adventure_card')

    def test_intro_can_be_skipped_or_finish_and_continue_does_not_replay_it(self):
        game = self.game
        for slot in ('auto', 1, 2, 3):
            game.save_manager.path_for(slot).unlink(missing_ok=True)
        game._button_action('adventure:start')
        self.assertEqual(game.scene, 'adventure_intro')
        self.assertEqual(game.save_manager.load('auto').adventure_step, 'intro')
        for language in ('zh_TW', 'en'):
            game.localizer.set_language(language)
            for time in (6, 18, 31):
                game.adventure.intro_time = time
                game._draw((0, 0))
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.adventure.card_key, 'briefing')
        self.assertEqual(game.state.adventure_step, 'lawn')
        self.key(pygame.K_RETURN)
        self.assertEqual(game.scene, 'explore')
        game._continue_game()
        self.assertEqual(game.scene, 'explore')
        self.assertEqual(game.state.adventure_step, 'lawn')
        game.state.adventure_step = 'intro'
        game.adventure.intro_time = 0
        game.scene = 'adventure_intro'
        game.adventure.advance_intro(INTRO_DURATION)
        self.assertEqual(game.adventure.card_key, 'briefing')

    def test_all_stops_signal_retry_and_the_single_ending(self):
        game = self.game
        game.state.adventure_step = 'lawn'
        for stop, next_key in zip(STOPS[:5], ('education', 'library', 'station', 'log', 'beacon')):
            if stop.building:
                self.interior(stop)
            else:
                self.outdoor(stop)
            self.assertEqual(game.state.adventure_step, next_key)
            self.key(pygame.K_RETURN)
            if stop.building:
                self.assertEqual(game.scene, 'interior')
                self.key(pygame.K_ESCAPE)
        self.outdoor(SIDE_STOPS[0])
        self.assertIn('student', game.state.adventure_sides)
        self.key(pygame.K_RETURN)
        self.outdoor(SIDE_STOPS[1])
        self.assertIn('garden', game.state.adventure_sides)
        self.key(pygame.K_RETURN)
        self.outdoor(STOPS[5])
        self.key(pygame.K_1)
        self.assertEqual(game.state.adventure_step, 'beacon')
        self.assertTrue(game.adventure.answer_feedback)
        self.key(pygame.K_2)
        self.assertEqual(game.state.adventure_step, 'beacon')
        self.assertIsNone(game.state.adventure_ending)
        for language in ('zh_TW', 'en'):
            game.localizer.set_language(language)
            game._draw((0, 0))
        self.key(pygame.K_3)
        self.assertEqual(game.state.adventure_step, 'report')
        self.assertEqual([game.adventure.beacon_on(t) for t in (100, 300, 520, 700, 950, 1100, 1850, 2500)], [True, False]*4)
        self.key(pygame.K_RETURN)
        self.outdoor(STOPS[6])
        self.key(pygame.K_RETURN)
        self.interior(STOPS[7])
        self.assertEqual(game.state.adventure_ending, ENDING_ID)
        self.assertEqual(game.adventure.card_key, 'ending')
        self.assertEqual(game.state.time_minutes, 7*60)
        saved = game.save_manager.load('auto')
        self.assertEqual(saved.adventure_ending, ENDING_ID)
        self.assertEqual(saved.adventure_sides, {'garden', 'student'})
        self.assertEqual(saved.zombie_stage, 0)
        self.assertFalse(any(game.localizer.missing_keys().values()))

    def test_main_and_side_targets_are_walkably_connected(self):
        world = self.game.world
        for stop in (*STOPS, *SIDE_STOPS):
            center = stop.position(world)
            self.assertFalse(world.collides(body_at(center)), stop.key)
        pending = {stop.key: stop.position(world) for stop in (*STOPS, *SIDE_STOPS)}
        visited = {SPAWN_TILE}
        frontier = deque(visited)
        while frontier and pending:
            x, y = frontier.popleft()
            position = pygame.Vector2(tile_center((x, y)))
            pending = {key: center for key, center in pending.items() if center.distance_to(position) >= 40}
            for cell in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                a, b = cell
                if cell not in visited and 0<=a<MAP_COLS and 0<=b<MAP_ROWS:
                    neighbor = pygame.Vector2(tile_center(cell))
                    if all(not world.collides(body_at(position.lerp(neighbor, i/8))) for i in range(1,9)):
                        visited.add(cell)
                        frontier.append(cell)
        self.assertFalse(pending)

    def test_existing_save_and_lake_rescue_keep_story_progress(self):
        game = self.game
        old = GameState.from_dict({'version': 4, 'zombie_chapter': {'stage': 4, 'health': 100}})
        self.assertEqual(old.adventure_step, 'inactive')
        self.assertEqual(old.zombie_stage, 4)
        game._set_state(old)
        game.state.adventure_step = 'log'
        game.state.health = 20
        enemy = game.zombies.enemies[0]
        game.state.player_x, game.state.player_y = enemy.position
        game.scene = 'explore'
        for _ in range(20):
            game._update_explore(.05)
            if game.state.health == 100:
                break
        self.assertEqual(game.state.health, 100)
        self.assertEqual(game.state.adventure_step, 'log')
        self.assertEqual(game.save_manager.load('auto').adventure_step, 'log')
