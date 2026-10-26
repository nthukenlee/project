from __future__ import annotations
from dataclasses import dataclass, field
from .constants import SAVE_VERSION, WORLD_WIDTH, WORLD_HEIGHT
from .content import QUESTS, ZONES, SPAWN_TILE, tile_center

def default_quest_states():
    return {q["id"]:{"status":"available","progress":[]} for q in QUESTS}

@dataclass
class GameState:
    player_x: float = field(default_factory=lambda: float(tile_center(SPAWN_TILE)[0]))
    player_y: float = field(default_factory=lambda: float(tile_center(SPAWN_TILE)[1]))
    facing: str = "down"
    language: str = "zh_TW"
    fullscreen: bool = False
    visited_zones: set[str] = field(default_factory=set)
    talked_to: set[str] = field(default_factory=set)
    discovered_landmarks: set[str] = field(default_factory=set)
    quest_states: dict = field(default_factory=default_quest_states)
    play_seconds: float = 0
    active_quest: str | None = "welcome"
    player_name: str = "小華"
    appearance: dict = field(default_factory=lambda:{"skin":1,"hair_style":0,"hair_color":0,"shirt":0,"pants":0})
    inventory_selected: int = 0
    hunger: float = 100
    thirst: float = 100
    difficulty: str = "normal"
    day: int = 1
    time_minutes: float = 8*60.0
    energy: float = 100
    supplies: dict = field(default_factory=lambda:{"water":3,"snack":2})
    photos: set[str] = field(default_factory=set)
    observations: set[str] = field(default_factory=set)

    def to_dict(self):
        return {
            "version":SAVE_VERSION,
            "player":{"x":self.player_x,"y":self.player_y,"facing":self.facing},
            "settings":{"language":self.language,"fullscreen":self.fullscreen},
            "profile":{"name":self.player_name,"appearance":self.appearance},
            "survival":{"hunger":self.hunger,"thirst":self.thirst,"difficulty":self.difficulty},
            "world_clock":{"day":self.day,"minutes":self.time_minutes},
            "energy":self.energy,"supplies":self.supplies,"inventory_selected":self.inventory_selected,
            "visited_zones":sorted(self.visited_zones),"talked_to":sorted(self.talked_to),
            "discovered_landmarks":sorted(self.discovered_landmarks),"quest_states":self.quest_states,
            "play_seconds":self.play_seconds,"active_quest":self.active_quest,
            "photos":sorted(self.photos),"observations":sorted(self.observations),
        }

    @classmethod
    def from_dict(cls, data):
        d = migrate_save(data)
        s = cls()
        player, settings, profile = d.get("player",{}), d.get("settings",{}), d.get("profile",{})
        x,y = float(player.get("x",s.player_x)), float(player.get("y",s.player_y))
        if 16 <= x < WORLD_WIDTH-16 and 16 <= y < WORLD_HEIGHT-16: s.player_x,s.player_y=x,y
        s.facing = player.get("facing","down")
        s.language = "en" if settings.get("language") == "en" else "zh_TW"
        s.fullscreen = bool(settings.get("fullscreen",False))
        s.player_name = str(profile.get("name","小華"))[:12] or "小華"
        for key, limit in (("skin",4),("hair_style",4),("hair_color",5),("shirt",6),("pants",4)):
            s.appearance[key] = int(profile.get("appearance",{}).get(key,s.appearance[key])) % limit
        survival, clock = d.get("survival",{}), d.get("world_clock",{})
        s.hunger = max(0,min(100,float(survival.get("hunger",100))))
        s.thirst = max(0,min(100,float(survival.get("thirst",100))))
        s.difficulty = survival.get("difficulty","normal")
        s.energy = max(0,min(100,float(d.get("energy",100))))
        s.day = max(1,int(clock.get("day",1)))
        s.time_minutes = max(0,min(1439,float(clock.get("minutes",480))))
        s.play_seconds = max(0,float(d.get("play_seconds",0)))
        s.inventory_selected = max(0,min(5,int(d.get("inventory_selected",0))))
        for key in ("visited_zones","talked_to","discovered_landmarks","photos","observations"):
            setattr(s,key,set(d.get(key,[])))
        if "main_library" in s.visited_zones: s.visited_zones.add("library")
        for q in QUESTS:
            old = d.get("quest_states",{}).get(q["id"],{})
            status = old.get("status","available")
            s.quest_states[q["id"]]["status"] = status if status in ("available","active","completed","locked") else "available"
        for kind in ("water","snack"): s.supplies[kind] = max(0,min(9,int(d.get("supplies",{}).get(kind,s.supplies[kind]))))
        QuestSystem(s).refresh()
        return s

def migrate_save(data):
    if not isinstance(data,dict): raise ValueError("Save data must be an object")
    version = int(data.get("version",0))
    if version > SAVE_VERSION: raise ValueError("Unsupported newer save version")
    migrated = dict(data)
    if version == 0:
        migrated["player"]={"x":migrated.get("player_x",tile_center(SPAWN_TILE)[0]),"y":migrated.get("player_y",tile_center(SPAWN_TILE)[1]),"facing":migrated.get("facing","down")}
    for key in ("collected","hidden_items","resources","gathered_nodes","crafted","decorations","area","courtyard_pos","courtyard_flags"):
        migrated.pop(key,None)
    if version < 2: migrated["inventory_selected"] = 0
    migrated["version"] = SAVE_VERSION
    return migrated

class QuestSystem:
    def __init__(self,state): self.state=state
    def activate_from_npc(self,npc_id):
        quest = next((q for q in QUESTS if q["giver"] == npc_id),None)
        if not quest: return None,None
        value = self.state.quest_states[quest["id"]]
        result = "active"
        if value["status"] in ("available","locked"):
            value["status"]="active"; self.state.active_quest=quest["id"]; result="accepted"
        elif value["status"] == "completed": result="completed"
        self.refresh()
        return quest["id"],result
    def record_visit(self,zone_id):
        self.state.visited_zones.add("library" if zone_id == "main_library" else zone_id)
        return self.refresh()
    def record_talk(self,npc_id):
        self.state.talked_to.add(npc_id)
        return self.refresh()
    def refresh(self):
        completed=[]
        for _ in range(2):
            for quest in QUESTS:
                value=self.state.quest_states[quest["id"]]
                if value["status"] != "active": continue
                if quest["kind"] in ("visit","talk"):
                    source=self.state.visited_zones if quest["kind"] == "visit" else self.state.talked_to
                    progress=[target for target in quest["targets"] if target in source]
                    done=len(progress)==len(quest["targets"])
                else:
                    count=sum(v["status"]=="completed" for key,v in self.state.quest_states.items() if key != quest["id"])
                    progress=[str(count)]; done=count>=quest["count"]
                value["progress"]=progress
                if done: value["status"]="completed"; completed.append(quest["id"])
        return completed
    def objective_progress(self,quest):
        if quest["kind"] in ("visit","talk"): return len(self.state.quest_states[quest["id"]]["progress"]),len(quest["targets"])
        count=sum(v["status"]=="completed" for key,v in self.state.quest_states.items() if key != quest["id"])
        return min(count,quest["count"]),quest["count"]
    def completion_percent(self):
        done=sum(v["status"]=="completed" for v in self.state.quest_states.values())
        visited=len(self.state.visited_zones & {z["id"] for z in ZONES})
        return min(100,round((done*4+visited)/(len(QUESTS)*4+len(ZONES))*100))
