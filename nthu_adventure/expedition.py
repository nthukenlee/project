"""Seeded campus encounters and their bilingual character pool."""
from collections import Counter
from dataclasses import dataclass
import json
from random import Random

from .constants import DATA_DIR

DATA = json.loads((DATA_DIR / "expedition_events.json").read_text(encoding="utf-8"))
ROOM_EVENTS = {key: tuple(events) for key, events in DATA["rooms"].items()}
OUTDOOR_POINTS = DATA["outdoor"]
OUTDOOR_CLUES = DATA["outdoor_clues"]
EVENTS = DATA["events"]
MAIN_STEPS = ("manifest", "echo_log", "lock_log", "sealed")
EXTRA_CLUES = ("marked_map", "arrival_times", "relay_tags", "empty_case", "torn_route", "return_tally")
STORY_STEPS = MAIN_STEPS + EXTRA_CLUES
MIN_ROUTE_STOPS, MAX_ROUTE_STOPS = 5, 8
MIN_OUTDOOR_EVENTS, MAX_OUTDOOR_EVENTS = 8, 12
OUTBREAK_SITES = ("lake", "lawn", "clock", "plaza")


def main_route(seed):
    rng = Random("refuge-route-expanded/" + str(seed))
    count = rng.randint(MIN_ROUTE_STOPS, MAX_ROUTE_STOPS)
    extras = rng.sample(EXTRA_CLUES, count - len(MAIN_STEPS))
    steps = (*MAIN_STEPS[:2], *extras, *MAIN_STEPS[2:])
    interior = rng.choice(sorted(ROOM_EVENTS))
    exterior = rng.choice(sorted(OUTDOOR_CLUES))
    available = sorted((set(ROOM_EVENTS) | set(OUTDOOR_CLUES)) - {interior, exterior})
    stops = [exterior, *rng.sample(available, count - 2)]
    rng.shuffle(stops)
    return dict(zip(steps, [*stops, interior], strict=True))


def valid_route(route):
    if not isinstance(route, dict):
        return False
    steps = tuple(route)
    places = tuple(route.values())
    if not set(steps) <= set(STORY_STEPS) or any(not isinstance(place, str) for place in places):
        return False
    if steps == MAIN_STEPS:
        # Keep a route already started on the four-stop release.
        return len(set(places)) == len(steps) and all(place in ROOM_EVENTS for place in places)
    return (
        MIN_ROUTE_STOPS <= len(steps) <= MAX_ROUTE_STOPS
        and steps[:2] == MAIN_STEPS[:2] and steps[-2:] == MAIN_STEPS[2:]
        and len(set(places)) == len(steps) and places[-1] in ROOM_EVENTS
        and any(place in OUTDOOR_CLUES for place in places)
        and all(place in ROOM_EVENTS or place in OUTDOOR_CLUES for place in places)
    )


def outbreak_site(seed):
    return Random("outbreak-site/" + str(seed)).choice(OUTBREAK_SITES)


def to_minutes(stamp):
    hour, minute = stamp.split(":")
    return int(hour) * 60 + int(minute)


EVENT_WINDOWS = {
    key: (to_minutes(item.get("after", "00:00")), to_minutes(item.get("before", "99:59")))
    for key, item in EVENTS.items()
}

# Each role has more than one possible name and voice. Motives belong to roles.
ROLE_MOTIVE = {
    "student": "helpful", "aide": "helpful", "worker": "helpful", "reader": "guarded",
    "resident": "helpful", "stranded": "panicked", "teammate": "helpful", "guard": "guarded",
    "guide": "helpful", "graduate": "guarded", "group": "guarded",
    "caretaker": "helpful", "hoarder": "selfish", "mimic": "mimic",
}
NAMES = (
    ("亭儀", "Ting-Yi", "female"), ("品妤", "Pin-Yu", "female"), ("艾晴", "Ai-Ching", "female"),
    ("若芸", "Jo-Yun", "female"), ("文倩", "Wen-Chien", "female"), ("安禾", "An-Ho", "female"),
    ("怡秋", "Yi-Chiu", "female"), ("宛真", "Wan-Chen", "female"), ("雅珊", "Ya-Shan", "female"),
    ("語柔", "Yu-Jou", "female"), ("展睿", "Chan-Rui", "male"), ("以辰", "Yi-Chen", "male"),
    ("明修", "Ming-Hsiu", "male"), ("承佑", "Cheng-Yu", "male"), ("睿安", "Rui-An", "male"),
    ("子皓", "Tzu-Hao", "male"), ("昱庭", "Yu-Ting", "male"), ("冠廷", "Kuan-Ting", "male"),
    ("朔民", "Shuo-Min", "male"), ("立洋", "Li-Yang", "male"),
    ("佳穎", "Chia-Ying", "female"), ("怡寧", "Yi-Ning", "female"), ("舒恩", "Shu-En", "female"),
    ("亦庭", "Yi-Ting", "female"), ("志齊", "Chih-Chi", "male"), ("景維", "Ching-Wei", "male"),
    ("哲倫", "Che-Lun", "male"), ("允成", "Yun-Cheng", "male"),
    ("思妍", "Szu-Yen", "female"), ("昀庭", "Yun-Ting", "female"), ("沛岑", "Pei-Tsen", "female"),
    ("品珊", "Pin-Shan", "female"), ("宇捷", "Yu-Chieh", "male"), ("宥真", "You-Chen", "female"),
    ("逸翔", "Yi-Hsiang", "male"), ("秉文", "Ping-Wen", "male"),
)
STOP_MINUTE = 17 * 60 + 45
SIGNAL_MINUTE = 17 * 60 + 47
DARK_MINUTE = 18 * 60
START_MINUTE = 17 * 60 + 42
MINUTE_SECONDS = 9
ENEMY_SPEED = .72


@dataclass
class Encounter:
    event: str
    role: str
    person: int
    status: str = "unseen"
    clock: int = 0
    outcome: str = ""

    @property
    def motive(self):
        return ROLE_MOTIVE[self.role]

    @property
    def activity(self):
        return EVENTS[self.event]["activity"]

    @property
    def actor_id(self):
        return "enc_" + self.event

    def available(self, run):
        if not run.outbreak or self.status == "resolved":
            return False
        if self.clock:
            return True
        starts, ends = EVENT_WINDOWS[self.event]
        delay = EVENTS[self.event].get("delay")
        if delay:
            starts = max(starts, START_MINUTE + int(run.outbreak_at / MINUTE_SECONDS) + self.delay(run.seed))
        return starts <= run.minute <= ends

    def delay(self, seed):
        span = EVENTS[self.event].get("delay")
        return Random(f"encounter-time/{seed}/{self.event}").randint(*span) if span else 0

    def name(self, language):
        return NAMES[self.person][int(language == "en")]

    @property
    def voice(self):
        return NAMES[self.person][2]


def choose_events(seed, previous=None):
    rng = Random("campus-events/" + str(seed))
    existing = dict(previous or {})
    assignments = {}
    types = Counter(event.activity for event in existing.values())
    rooms = list(ROOM_EVENTS)
    rng.shuffle(rooms)
    for area in rooms:
        if area in existing:
            continue
        variants = ROOM_EVENTS[area]
        event = rng.choices(variants, weights=[1 / (1 + types[EVENTS[item]["activity"]]) for item in variants])[0]
        assignments[area] = event
        types[EVENTS[event]["activity"]] += 1
    outdoors = [key for key in existing if key in OUTDOOR_POINTS]
    outdoor_count = Random(f"outdoor-count/{seed}").randint(MIN_OUTDOOR_EVENTS, MAX_OUTDOOR_EVENTS)
    if len(outdoors) < outdoor_count:
        remaining = [key for key in OUTDOOR_POINTS if key not in outdoors]
        outdoors.extend(rng.sample(remaining, outdoor_count - len(outdoors)))
    assignments.update({event: event for event in outdoors})
    used = {event.person for event in existing.values()}
    available = [person for person in range(len(NAMES)) if person not in used]
    rng.shuffle(available)
    for key, event in assignments.items():
        if key not in existing:
            existing[key] = Encounter(event, rng.choice(EVENTS[event]["roles"]), available.pop())
    return existing
