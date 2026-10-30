"""Campus geometry and observation/conversation activities. No pickup objects."""
from __future__ import annotations
from dataclasses import dataclass
import json
from .constants import DATA_DIR, MAP_COLS, MAP_ROWS, TILE

@dataclass(frozen=True)
class RectSpec:
    x: int
    y: int
    w: int
    h: int
    def pixels(self):
        return self.x*TILE, self.y*TILE, self.w*TILE, self.h*TILE

_layout = json.loads((DATA_DIR / "campus_layout.json").read_text(encoding="utf-8"))
ZONES = _layout["zones"]
ROADS = _layout["roads"]
WATERS = _layout["waters"]
ISLANDS = _layout["islands"]
WALKWAYS = _layout["walkways"]
LAKE_FEATURES = _layout["lake_features"]
LANDSCAPES = _layout.get('landscapes',[])
SCENERY_POINTS = _layout.get('scenery_points',[])
LAKE_POINTS = LAKE_FEATURES + [
    {"id":v["id"],"label":v["label"],"tile":v["center"]} for v in ISLANDS
] + [{"id":"west_entry","label":"lake.west_entry","tile":_layout["points"]["lake_entrance"]}]
SPORTS_FIELDS = [RectSpec(*v) for v in _layout["sports_fields"]]
BUILDINGS = [{**v, "rect": RectSpec(*v["rect"])} for v in _layout["buildings"]]
MAIN_GATE_TILE = tuple(_layout["points"]["main_gate"])
LAKE_ENTRANCE_TILE = tuple(_layout["points"]["lake_entrance"])
SPAWN_TILE = MAIN_GATE_TILE
NPCS = [
    {"id":"guide","tile":[31,104],"name":"npc.guide","dialog":"dialog.guide"},
    {"id":"librarian","tile":[78,78],"name":"npc.librarian","dialog":"dialog.librarian"},
    {"id":"photographer","tile":[58,88],"name":"npc.photographer","dialog":"dialog.photographer"},
    {"id":"professor","tile":[69,55],"name":"npc.professor","dialog":"dialog.professor"},
    {"id":"runner","tile":[126,76],"name":"npc.runner","dialog":"dialog.runner"},
    {"id":"engineer","tile":[120,57],"name":"npc.engineer","dialog":"dialog.engineer"},
    {"id":"artist","tile":[57,36],"name":"npc.artist","dialog":"dialog.artist"},
    {"id":"roommate","tile":[37,38],"name":"npc.roommate","dialog":"dialog.roommate"},
    {"id":"vendor","tile":[50,68],"name":"npc.vendor","dialog":"dialog.vendor"},
    {"id":"researcher","tile":[118,25],"name":"npc.researcher","dialog":"dialog.researcher"},
    {"id":"alumnus","tile":[57,84],"name":"npc.alumnus","dialog":"dialog.alumnus"},
    {"id":"birdwatcher","tile":[28,72],"name":"npc.birdwatcher","dialog":"dialog.birdwatcher"},
    {"id":"club_leader","tile":[24,58],"name":"npc.club_leader","dialog":"dialog.club_leader"},
    {"id":"caretaker","tile":[55,16],"name":"npc.caretaker","dialog":"dialog.caretaker"},
    {"id":"student","tile":[96,48],"name":"npc.student","dialog":"dialog.student"},
]
QUESTS = [
    {"id":"welcome","giver":"guide","title":"quest.welcome.title","desc":"quest.welcome.desc","kind":"visit","targets":["main_gate","admin","library"]},
    {"id":"lake_memories","giver":"photographer","title":"quest.lake.title","desc":"quest.lake.desc","kind":"visit","targets":["success_lake","activity","sports"]},
    {"id":"book_route","giver":"librarian","title":"quest.book.title","desc":"quest.book.desc","kind":"talk","targets":["photographer","professor","artist"]},
    {"id":"campus_history","giver":"alumnus","title":"quest.history.title","desc":"quest.history.desc","kind":"visit","targets":["humanities","academic","engineering"]},
    {"id":"morning_run","giver":"runner","title":"quest.run.title","desc":"quest.run.desc","kind":"visit","targets":["sports","north_woods","dorms"]},
    {"id":"lab_samples","giver":"researcher","title":"quest.lab.title","desc":"quest.lab.desc","kind":"visit","targets":["south_campus","engineering","success_lake"]},
    {"id":"club_posters","giver":"club_leader","title":"quest.club.title","desc":"quest.club.desc","kind":"talk","targets":["artist","engineer","roommate"]},
    {"id":"grand_tour","giver":"caretaker","title":"quest.grand.title","desc":"quest.grand.desc","kind":"complete_quests","count":7},
]
for npc in NPCS:
    npc["tile"] = _layout["npc_positions"][npc["id"]]
SHOPS = _layout["shops"]
DORMS = json.loads((DATA_DIR / "dorm_architecture.json").read_text(encoding="utf-8"))
ARCHITECTURE = json.loads((DATA_DIR / 'campus_architecture.json').read_text(encoding='utf-8'))

def tile_center(tile):
    return tile[0]*TILE + TILE//2, tile[1]*TILE + TILE//2

def validate_content():
    errors, ids = [], set()
    if (_layout["meta"]["columns"], _layout["meta"]["rows"]) != (MAP_COLS, MAP_ROWS):
        errors.append("Layout dimensions differ from runtime dimensions")
    for items in (ZONES, BUILDINGS, NPCS, QUESTS, ROADS, WATERS, ISLANDS, WALKWAYS, LAKE_FEATURES):
        for item in items:
            if item["id"] in ids: errors.append("Duplicate id: " + item["id"])
            ids.add(item["id"])
    for npc in NPCS:
        if not (0 <= npc["tile"][0] < MAP_COLS and 0 <= npc["tile"][1] < MAP_ROWS): errors.append(npc["id"])
    for feature in ROADS + WATERS + ISLANDS + WALKWAYS:
        if len(feature["points"]) < 2: errors.append(feature["id"])
        if not all(0 <= x < MAP_COLS and 0 <= y < MAP_ROWS for x,y in feature["points"]): errors.append(feature["id"])
    for quest in QUESTS:
        valid = {v["id"] for v in (ZONES if quest["kind"] == "visit" else NPCS)}
        if quest["kind"] in ("visit","talk") and not set(quest["targets"]) <= valid: errors.append(quest["id"])
    return errors
