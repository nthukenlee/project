import os
import tempfile
import unittest
from collections import deque
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')

from nthu_adventure import content
from nthu_adventure.content import BUILDINGS,NPCS,QUESTS,DORMS,SPAWN_TILE,tile_center,validate_content
from nthu_adventure.constants import SAVE_VERSION,TILE,MAP_COLS,MAP_ROWS
from nthu_adventure.state import GameState,QuestSystem,migrate_save
from nthu_adventure.savegame import SaveManager
from nthu_adventure.localization import Localizer

TEMP_ROOT=Path(__file__).resolve().parents[1]/'work'/'test-temp'
TEMP_ROOT.mkdir(parents=True,exist_ok=True)

class ContentTests(unittest.TestCase):
    def test_data_and_removed_pickups(self):
        self.assertEqual(validate_content(),[])
        self.assertEqual(len(BUILDINGS),26)
        self.assertEqual(len(QUESTS),8)
        for removed in ('COLLECTIBLES','RESOURCE_NODES','HIDDEN_ITEMS','RECIPES'):
            self.assertFalse(hasattr(content,removed),removed)
        self.assertTrue(all(q['kind'] in ('visit','talk','complete_quests') for q in QUESTS))

    def test_dorms_have_distinct_official_references(self):
        self.assertEqual(set(DORMS),{'ren_hall','shi_hall','li_hall','yi_hall'})
        self.assertEqual(len({d['source'] for d in DORMS.values()}),4)
        self.assertTrue(all(d['source'].startswith('https://sthousing.site.nthu.edu.tw/') for d in DORMS.values()))
        self.assertIn('疊層半圓玻璃窗帶',DORMS['yi_hall']['features'])
        self.assertIn('圓弧樓梯塔',DORMS['ren_hall']['features'])

    def test_languages_match(self):
        l=Localizer()
        self.assertEqual(l.missing_keys(),{'zh_TW':set(),'en':set()})
        self.assertNotIn('拾光',l.t('dialog.librarian'))
        l.set_language('en')
        self.assertEqual(l.t('v5.tool.camera'),'Camera')

class StateTests(unittest.TestCase):
    def test_old_inventory_is_removed_without_losing_profile_or_quests(self):
        old=GameState().to_dict()
        old.update(version=1,collected=['memory_01'],resources={'flower':999},crafted=['campus_lantern'],gathered_nodes=['resource_01'],hidden_items=['lake_pearl'],decorations={'ren_hall':[]},area='courtyard',inventory_selected=7)
        old['profile']['name']='測試玩家'
        old['quest_states']['welcome']['status']='completed'
        loaded=GameState.from_dict(old)
        self.assertEqual(loaded.player_name,'測試玩家')
        self.assertEqual(loaded.quest_states['welcome']['status'],'completed')
        self.assertEqual(loaded.inventory_selected,0)
        for removed in ('collected','resources','crafted','gathered_nodes','hidden_items','decorations','area'):
            self.assertNotIn(removed,loaded.to_dict())
            self.assertFalse(hasattr(loaded,removed))

    def test_all_quests_finish_through_visits_and_conversations(self):
        state=GameState(); quests=QuestSystem(state)
        for npc in NPCS: quests.activate_from_npc(npc['id']); quests.record_talk(npc['id'])
        for zone in content.ZONES: quests.record_visit(zone['id'])
        quests.refresh()
        self.assertTrue(all(value['status']=='completed' for value in state.quest_states.values()))
        self.assertEqual(quests.completion_percent(),100)

    def test_legacy_flat_save_and_newer_version(self):
        old=migrate_save({'player_x':800,'player_y':900})
        self.assertEqual(old['version'],SAVE_VERSION)
        self.assertEqual(old['player']['x'],800)
        with self.assertRaises(ValueError): migrate_save({'version':999})

    def test_save_roundtrip_and_corrupt_backup(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            manager=SaveManager(Path(directory)); state=GameState()
            state.player_name='清華'; state.photos={'ren_hall'}; state.observations={'ren_hall:desk'}
            state.visited_zones={'dorms'}; state.appearance['hair_style']=2
            manager.save(state,1); loaded=manager.load(1)
            self.assertEqual(loaded.to_dict(),state.to_dict())
            manager.path_for(2).write_text('{broken',encoding='utf-8')
            self.assertIsNone(manager.load(2))
            self.assertTrue(list(Path(directory).glob('slot_2.corrupt-*.json')))

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        from nthu_adventure.app import Game
        cls.directory=tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        cls.game=Game(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls):
        import pygame
        pygame.quit(); cls.directory.cleanup()

    def test_native_2d_scenes_and_no_pickup_callbacks(self):
        g=self.game
        for removed in ('_check_collectibles','_check_hidden_items','_craft_item','_courtyard_tool'):
            self.assertFalse(hasattr(g,removed))
        for language in ('zh_TW','en'):
            g.localizer.set_language(language)
            for scene in ('title','explore','map','notebook','guide','settings','customize','pause','save_menu'):
                g.scene=scene; g._draw((0,0))
                self.assertEqual(g.canvas.get_size(),(1280,720))
        g.localizer.set_language('zh_TW')

    def test_all_npcs_and_doors_reachable(self):
        import pygame
        world=self.game.world
        def open_tile(tile):
            x,y=tile_center(tile)
            return not world.collides(pygame.Rect(x-8,y-6,16,13))
        reachable={SPAWN_TILE}; frontier=deque([SPAWN_TILE])
        while frontier:
            x,y=frontier.popleft()
            for point in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if 0<=point[0]<MAP_COLS and 0<=point[1]<MAP_ROWS and point not in reachable and open_tile(point):
                    reachable.add(point); frontier.append(point)
        for npc in NPCS: self.assertIn(tuple(npc['tile']),reachable,npc['id'])
        for building in BUILDINGS:
            door=world.door(building)
            self.assertTrue(any(pygame.Vector2(tile_center(tile)).distance_to(door)<60 for tile in reachable),building['id'])

    def test_dorm_entry_read_rest_and_exit_without_items(self):
        import pygame
        g=self.game
        for key in DORMS:
            g._travel(key)
            door=g.world.door(next(b for b in BUILDINGS if b['id']==key))
            g.state.player_x,g.state.player_y=door
            g._interact()
            self.assertEqual(g.scene,'interior')
            self.assertEqual(g.current_interior['id'],key)
            g.room_position=pygame.Vector2(.35,.66); g._interact_interior()
            self.assertIn(key+':desk',g.state.observations)
            g.state.energy=10; g.room_position=pygame.Vector2(.35,.39); g._interact_interior()
            self.assertEqual(g.state.energy,100)
            g._draw((0,0)); g._button_action('leave')
            self.assertEqual(g.scene,'explore')

    def test_old_pickup_location_does_not_create_items(self):
        g=self.game
        g.state=GameState(); g.quests=QuestSystem(g.state)
        g.state.player_x,g.state.player_y=tile_center((22,105))
        g._update_explore(.01)
        self.assertFalse(hasattr(g.state,'collected'))
        self.assertNotIn('collected',g.state.to_dict())

if __name__=='__main__': unittest.main()
