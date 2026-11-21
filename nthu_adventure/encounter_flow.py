"""Resolve campus encounters into choices, follow-up routes and persistent outcomes."""

from pygame import Vector2

from .expedition import EVENTS, MINUTE_SECONDS, NAMES, OUTDOOR_POINTS
from .survival import Actor, INFECTION_SECONDS, body, distance, visible


class EncounterFlow:
    def __init__(self, game):
        self.game = game
        self.outdoors = {key: game.slots.near(Vector2(tile) * 32) for key, tile in OUTDOOR_POINTS.items()}
        self.pins = {**game.slots.outdoor_clues}
        for key, tile in {"trail_plaza": (106, 64), "trail_sports": (53, 54),
                          "trail_materials": (61, 46)}.items():
            self.pins[key] = game.slots.near(Vector2(tile) * 32)
        self.pins["trail_dorm"] = self.pins["trail_residence"]

    @property
    def state(self):
        return self.game.run_state

    def locations(self):
        state = self.state
        if state.area == "campus":
            for key, event in state.encounters.items():
                if key in self.outdoors:
                    yield key, event, self.outdoors[key]
        elif state.area in state.encounters:
            yield state.area, state.encounters[state.area], self.game.rooms[state.area].event_point

    def sync(self):
        state = self.state
        for _, event, point in self.locations():
            if not event.available(state) or distance(point, state.position) > 480:
                continue
            if event.actor_id not in state.actors:
                state.actors[event.actor_id] = Actor(event.role, point, state.area, identity=event.person)
            if event.event == "campus_rain" and not event.clock and distance(point, state.position) <= 84:
                state.storm_until = max(state.storm_until, state.elapsed + 38)
                event.clock = state.minute

    def targets(self):
        state = self.state
        for key, event, point in self.locations():
            actor = state.actors.get(event.actor_id)
            if event.available(state) and (actor is None or actor.status == "waiting"):
                yield "encounter", key, point

    def encounter_for_actor(self, actor_id):
        actor_id = actor_id.removesuffix("_perimeter")
        return next((event for event in self.state.encounters.values() if event.actor_id == actor_id), None)

    def person_name(self, actor_id, event):
        language = self.game.localizer.language
        if actor_id.endswith("_perimeter"):
            return NAMES[self.state.actors[actor_id].identity][int(language == "en")]
        return event.name(language)

    @staticmethod
    def title(event):
        return f"encounter.{event.event}.title"

    def open(self, key):
        event = self.state.encounters[key]
        if not event.available(self.state):
            return
        self.sync()
        if not event.clock:
            event.clock = self.state.minute
        event.status = "heard"
        self.game.show(self.title(event), f"encounter.{event.event}.text", self.options(key, event),
                       speaker=event.name(self.game.localizer.language))

    @staticmethod
    def options(key, event):
        return tuple(f"event_{option}/{key}" for option in EVENTS[event.event].get("choices", {}))

    def option_label(self, action):
        number, key = action.removeprefix("event_").split("/", 1)
        return self.game.tr(f"encounter.{self.state.encounters[key].event}.option_{number}")

    def resolve(self, action, key):
        state = self.state
        event = state.encounters[key]
        person = state.actors.get(event.actor_id)
        self.game.scene = "play"
        if not event.available(state) or person is None or person.status != "waiting":
            return
        choice = EVENTS[event.event].get("choices", {}).get(action)
        if choice is None:
            return
        result = self.apply(key, event, person, choice["operation"], choice.get("arg", ""))
        if result:
            self.finish(event, result)

    def result_key(self, event):
        specific = f"encounter.{event.event}.{event.outcome}"
        catalog = self.game.localizer.catalogs[self.game.localizer.language]
        return specific if "survival." + specific in catalog else "exp.result." + event.outcome

    def finish(self, event, outcome):
        event.status, event.outcome = "resolved", outcome
        self.game.show(self.title(event), self.result_key(event), speaker=event.name(self.game.localizer.language))

    def set_pin(self, name):
        self.state.event_progress["waypoint"] = ("campus", self.pins[name])

    def waypoint(self):
        progress = self.state.event_progress
        if drop := progress.get("parcel_drop"):
            return drop
        mission = progress.get("mission")
        return (mission["area"], mission["point"]) if mission else progress.get("waypoint")

    def begin_task(self, key, event, kind, area, point, *, actor=None, limit=None, guard=None):
        state = self.state
        state.event_progress["mission"] = {
            "key": key, "actor": actor or event.actor_id, "kind": kind, "area": area, "point": tuple(point),
            "until": state.elapsed + limit if limit else None, "guard": guard,
        }
        state.event_progress.pop("waypoint", None)
        return "task_" + kind

    def followups(self):
        progress = self.state.event_progress
        mission = progress.get("mission")
        drop = progress.get("parcel_drop")
        if drop:
            if drop[0] == self.state.area:
                yield "event_point", "task_parcel_pickup", drop[1]
            return
        if mission and mission["area"] == self.state.area:
            yield "event_point", "task_" + mission["kind"], mission["point"]

    def drop_parcel(self):
        state = self.state
        if state.event_progress.pop("carrying_parcel", None):
            state.event_progress["parcel_drop"] = (state.area, state.position)
            self.game.notify("event.parcel_dropped")
            return True
        return False

    def end_task(self, mission, outcome):
        state = self.state
        state.event_progress.pop("mission", None)
        state.event_progress.pop("waypoint", None)
        if mission["kind"] == "parcel":
            state.event_progress.pop("carrying_parcel", None)
            state.event_progress.pop("parcel_drop", None)
        event = state.encounters[mission["key"]]
        event.outcome = outcome
        self.game.notify(self.result_key(event))

    def advance(self):
        state = self.state
        mission = state.event_progress.get("mission")
        if not mission:
            return False
        person = state.actors.get(mission["actor"])
        unavailable = (mission["kind"] in ("lawn", "rescue_bat", "rescue_detour", "care", "outdoor_escort")
                       and (not person or person.status in ("turned", "gone")))
        if person and mission["kind"].startswith("rescue") and person.status == "bitten":
            unavailable = True
        expired = mission["until"] is not None and state.elapsed >= mission["until"]
        if expired or unavailable:
            if expired and person and person.status == "waiting" and mission["kind"].startswith("rescue"):
                person.status = "turned"
                person.kind = "hunter"
            self.end_task(mission, "task_missed")
            return True
        return False

    def complete(self, key):
        state = self.state
        mission = state.event_progress.get("mission")
        if not mission or self.advance():
            return
        kind = mission["kind"]
        actor = state.actors.get(mission["actor"])
        if kind == "parcel":
            if key == "task_parcel_pickup":
                state.event_progress.pop("parcel_drop", None)
                state.event_progress["carrying_parcel"] = True
                self.game.notify("exp.result.task_parcel")
                return
            state.add_gear("food")
            outcome = "parcel_delivered"
        elif kind == "wrong_list":
            mission.update(kind="right_list", point=tuple(self.pins["trail_clock"]))
            state.encounters[mission["key"]].outcome = "list_wrong"
            self.game.notify("exp.result.list_wrong")
            return
        elif kind == "right_list":
            outcome = "list_confirmed"
        elif kind == "care":
            actor.choice = "separate"
            actor.status = "gone"
            self.end_task(mission, "bite_settled")
            self.set_pin("trail_residence")
            return
        elif kind in ("lawn", "outdoor_escort"):
            if actor.status != "joined" or actor.area != state.area or distance(actor.position, state.position) > 110:
                self.game.notify("event.wait_for_person")
                return
            slow_route = actor.choice == "lawn_slow"
            actor.choice = "join"
            outcome = "lawn_safe" if slow_route else "lawn_done" if kind == "lawn" else "escort_complete"
            if slow_route:
                self.end_task(mission, outcome)
                self.set_pin("trail_plaza")
                return
        else:
            guard = state.actors.get(mission["guard"])
            if kind == "rescue_bat" and guard and not guard.stunned:
                self.game.notify("event.stun_guard_first")
                return
            if len(state.team) >= 2:
                self.game.notify("event.team_full")
                return
            actor.status, actor.choice = "joined", "join"
            outcome = "rescue_done"
        self.end_task(mission, outcome)

    def apply(self, key, event, person, action, arg):
        state = self.state
        game = self.game
        if action in ("recruit", "escort", "lawn_fast", "lawn_slow", "bite_keep", "bite_care"):
            if len(state.team) >= 2:
                game.notify("event.team_full")
                return None
        if action in ("parcel", "list_walk", "list_check", "lawn_fast", "lawn_slow", "bite_care",
                      "rescue_bat", "rescue_detour") or (action == "escort" and state.area == "campus"):
            if "mission" in state.event_progress:
                game.notify("event.finish_existing_task")
                return None
        if action in ("trade", "rest_cost"):
            spend, _, receive = arg.partition(":")
            if not state.pack[spend]:
                game.notify("exp.missing", item=game.tr("gear." + spend))
                return None
            state.pack[spend] -= 1
            if receive:
                state.add_gear(receive)
                return "exchange_water" if receive == "water" else "exchange_food"
            state.stamina = min(100, state.stamina + 35)
            return "rest_traded"
        if action in ("mark", "mark_cost", "effort_mark", "work", "effort"):
            if action != "mark":
                cost, arg = arg.split(":")
                cost = int(cost)
                if action.startswith("effort"):
                    if state.stamina < cost:
                        game.notify("event.too_tired")
                        return None
                    state.stamina -= cost
                else:
                    state.spend_time(cost)
            if action in ("mark", "mark_cost", "effort_mark"):
                self.set_pin(arg)
                return "route_marked"
            state.add_gear(arg)
            return "work_water" if arg == "water" else "work_food"
        if action == "shelter":
            state.spend_time(12)
            state.stamina = min(100, state.stamina + 50)
            return "rested"
        if action == "evacuate":
            state.spend_time(int(arg))
            person.status = "gone"
            return "evacuated"
        if action in ("recruit", "escort"):
            person.status, person.choice = "joined", "join" if action == "recruit" else "escort"
            if action == "escort" and state.area == "campus":
                person.choice = "join"
                return self.begin_task(key, event, "outdoor_escort", "campus",
                                       self.pins["trail_residence"], limit=55)
            return "escort" if action == "escort" else "joined"
        if action == "parcel":
            state.event_progress["carrying_parcel"] = True
            return self.begin_task(key, event, "parcel", state.area, game.slots.event_points[state.area][1])
        if action.startswith("list_"):
            if action == "list_check":
                state.spend_time(MINUTE_SECONDS)
                return self.begin_task(key, event, "right_list", "campus", self.pins["trail_clock"])
            return self.begin_task(key, event, "wrong_list", "campus", self.pins["trail_library"])
        if action.startswith("lawn_"):
            fast = action == "lawn_fast"
            if not fast:
                other_id = event.actor_id + "_perimeter"
                state.actors[other_id] = Actor("graduate", person.position, "campus",
                                                identity=(person.identity+1) % len(NAMES))
                person.status = "gone"
                person = state.actors[other_id]
            else:
                other_id = event.actor_id
            person.status, person.choice = "joined", "lawn_fast" if fast else "lawn_slow"
            point = self.game.slots.near(Vector2((118, 62) if fast else (131, 65)) * 32)
            return self.begin_task(key, event, "lawn", "campus", point, actor=other_id, limit=40 if fast else 52)
        if action.startswith("rescue_"):
            if len(state.team) >= 2:
                game.notify("event.team_full")
                return None
            if action == "rescue_bat" and not state.pack["bat"]:
                game.notify("event.empty_bat")
                return None
            near, far = game.slots.event_points[state.area]
            person.position = tuple(near if action == "rescue_bat" else far)
            guard_id = event.actor_id + "_guard"
            guard_point = near
            if action == "rescue_bat":
                hit = game.rooms[state.area].hit
                targets = [Vector2(near) + shift for shift in ((42, 0), (-42, 0), (0, 42), (0, -42))]
                guard_point = next((point for point in targets if not hit(body(point)) and visible(point, near, hit)), near)
            state.actors[guard_id] = Actor("hunter", tuple(guard_point),
                                           state.area, status="hostile")
            return self.begin_task(key, event, action, state.area, person.position,
                                   limit=27 if action == "rescue_bat" else 32, guard=guard_id)
        if action.startswith("bite_"):
            if action == "bite_leave":
                person.status = "gone"
                return "bite_left"
            person.status, person.choice = "bitten", "join"
            person.infection = INFECTION_SECONDS
            if action == "bite_care":
                # The nearby rest point is reachable during the short infection window.
                return self.begin_task(key, event, "care", state.area, game.slots.rest_points[state.area],
                                       limit=INFECTION_SECONDS)
            return "bite_risk"
        return None
