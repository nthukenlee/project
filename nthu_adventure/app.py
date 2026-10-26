"""Hand-painted, native-resolution 2D exploration, conversation and observation."""
from __future__ import annotations
import math
from pathlib import Path
import pygame
from .constants import INTERNAL_WIDTH, INTERNAL_HEIGHT, WINDOW_SIZE, FPS, TILE, WORLD_WIDTH, WORLD_HEIGHT
from .content import BUILDINGS, NPCS, QUESTS, ZONES, SHOPS, DORMS, tile_center, validate_content
from .state import GameState, QuestSystem
from .savegame import SaveManager
from .localization import Localizer
from .paperworld import PaperWorld
from .audio import AudioManager
from .ui import Button, FontBook, panel, INK, PAPER, MUTED, GREEN

class Game:
    def __init__(self,save_dir: Path|None=None):
        if errors:=validate_content(): raise ValueError(str(errors))
        pygame.init()
        pygame.display.set_caption('清華拾光 · 2D 手繪漫遊')
        self.screen=pygame.display.set_mode(WINDOW_SIZE,pygame.RESIZABLE)
        self.canvas=pygame.Surface(WINDOW_SIZE)
        self.clock=pygame.time.Clock()
        self.fonts=FontBook(); self.localizer=Localizer(); self.save_manager=SaveManager(save_dir)
        self.world=PaperWorld(); self.audio=AudioManager()
        self.state=GameState(); self.quests=QuestSystem(self.state)
        self.scene='title'; self.previous_scene='title'; self.panel_tab='map'
        self.running=True; self.fullscreen=False; self.player_moving=False; self.riding_bike=False
        self.buttons=[]; self.inventory_rects=[]
        self.notification=''; self.notification_until=0; self.last_autosave=0
        self.dialog_speaker=''; self.dialog_lines=[]
        self.current_interior=None; self.room_position=pygame.Vector2(.5,.80)
        self.room_rect=pygame.Rect(330,74,620,620)
        self.custom_name=''; self.custom_appearance=dict(self.state.appearance)
        self.selected_dorm='ren_hall'

    @property
    def t(self): return self.localizer.t

    def run(self):
        while self.running:
            dt=min(self.clock.tick(FPS)/1000,.05)
            mouse=self._mouse_internal()
            for event in pygame.event.get(): self._handle_event(event,mouse)
            if self.scene=='explore': self._update_explore(dt)
            elif self.scene=='interior': self._update_interior(dt)
            self._draw(mouse); self._present()
        if self.state.play_seconds>0: self.save_manager.save(self.state,'auto')
        pygame.quit()

    def _viewport(self):
        w,h=self.screen.get_size(); scale=min(w/1280,h/720)
        return pygame.Rect(round((w-1280*scale)/2),round((h-720*scale)/2),round(1280*scale),round(720*scale))

    def _mouse_internal(self):
        view=self._viewport(); x,y=pygame.mouse.get_pos()
        if not view.collidepoint(x,y): return (-1000,-1000)
        return round((x-view.x)*1280/view.width),round((y-view.y)*720/view.height)

    def _present(self):
        self.screen.fill((26,37,33)); view=self._viewport()
        image=self.canvas if view.size==WINDOW_SIZE else pygame.transform.smoothscale(self.canvas,view.size)
        self.screen.blit(image,view); pygame.display.flip()

    def _set_fullscreen(self,enabled):
        self.fullscreen=bool(enabled); self.state.fullscreen=self.fullscreen
        self.screen=pygame.display.set_mode((0,0) if enabled else WINDOW_SIZE,pygame.FULLSCREEN if enabled else pygame.RESIZABLE)

    def _set_state(self,state):
        self.state=state; self.quests=QuestSystem(state); self.localizer.set_language(state.language)
        if self.fullscreen!=state.fullscreen: self._set_fullscreen(state.fullscreen)
        self._ensure_walkable()

    def _ensure_walkable(self):
        if not self.world.collides(self._player_rect()): return
        start=pygame.Vector2(self.state.player_x,self.state.player_y)
        for distance in range(16,320,16):
            for direction in ((0,1),(1,0),(-1,0),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                point=start+pygame.Vector2(direction)*distance
                if not self.world.collides(self._player_rect(point.x,point.y)):
                    self.state.player_x,self.state.player_y=point; return
        self.state.player_x,self.state.player_y=tile_center((27,106))

    def _new_game(self):
        self._set_state(GameState(language=self.localizer.language,fullscreen=self.fullscreen,player_name=self.custom_name.strip()[:12] or '小華',appearance=dict(self.custom_appearance)))
        self.quests.activate_from_npc('guide'); self.scene='explore'
        pygame.key.stop_text_input(); self._notify(self.t('v5.welcome')); self.save_manager.save(self.state,'auto')

    def _continue_game(self):
        slot=self.save_manager.newest_available()
        state=self.save_manager.load(slot) if slot is not None else None
        if state: self._set_state(state); self.scene='explore'
        else: self._new_game()

    def _handle_event(self,event,mouse):
        if event.type==pygame.QUIT: self.running=False; return
        if event.type==pygame.TEXTINPUT and self.scene=='customize':
            self.custom_name=(self.custom_name+''.join(c for c in event.text if c.isprintable()))[:12]
        if event.type==pygame.KEYDOWN:
            key=event.key
            if key==pygame.K_F11: self._set_fullscreen(not self.fullscreen); return
            if self.scene=='customize':
                if key==pygame.K_BACKSPACE: self.custom_name=self.custom_name[:-1]
                elif key==pygame.K_RETURN: self._new_game()
                elif key==pygame.K_ESCAPE: pygame.key.stop_text_input(); self.scene='title'
            elif self.scene=='explore':
                if key in (pygame.K_e,pygame.K_RETURN): self._interact()
                elif key==pygame.K_m: self.scene='map'
                elif key==pygame.K_q: self.scene='notebook'
                elif key==pygame.K_c: self.scene='guide'
                elif key==pygame.K_SPACE: self._use_selected_item()
                elif key==pygame.K_b: self._use_tool('bike')
                elif key==pygame.K_ESCAPE: self.scene='pause'
                elif pygame.K_1<=key<=pygame.K_6: self.state.inventory_selected=key-pygame.K_1
            elif self.scene=='interior':
                if key==pygame.K_ESCAPE: self._leave_special_area()
                elif key in (pygame.K_e,pygame.K_RETURN): self._interact_interior()
            elif self.scene=='dialog':
                if key in (pygame.K_e,pygame.K_RETURN,pygame.K_SPACE,pygame.K_ESCAPE): self.scene='explore'
            elif key==pygame.K_ESCAPE:
                self.scene=self.previous_scene if self.scene in ('settings','save_menu') else 'explore'
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if self.scene=='dialog': self.scene='explore'; return
            for button in self.buttons:
                if button.enabled and button.rect.collidepoint(mouse):
                    self.audio.play('select'); self._button_action(button.action); return
            if self.scene=='map': self._map_click(mouse)

    def _button_action(self,action):
        if action=='new':
            self.custom_name=''; self.custom_appearance=dict(GameState().appearance)
            pygame.key.start_text_input(); self.scene='customize'
        elif action=='custom_start': self._new_game()
        elif action=='continue': self._continue_game()
        elif action=='dorm_tour':
            self._continue_game(); self._travel('ren_hall')
        elif action=='quit': self.running=False
        elif action in ('resume','close'): self.scene='explore'
        elif action=='leave': self._leave_special_area()
        elif action=='title': self.save_manager.save(self.state,'auto'); self.scene='title'
        elif action=='settings': self.previous_scene=self.scene; self.scene='settings'
        elif action=='back': self.scene=self.previous_scene
        elif action=='save_menu': self.previous_scene='pause'; self.scene='save_menu'
        elif action=='language':
            self.localizer.set_language('en' if self.localizer.language=='zh_TW' else 'zh_TW'); self.state.language=self.localizer.language
        elif action=='fullscreen': self._set_fullscreen(not self.fullscreen)
        elif action.startswith('slot:'):
            slot=int(action.split(':')[1]); self.save_manager.save(self.state,slot); self._notify(self.t('menu.saved')); self.scene='pause'
        elif action.startswith('travel:'): self._travel(action.split(':')[1])
        elif action.startswith('dorm:'): self.selected_dorm=action.split(':')[1]
        elif action.startswith('tool:'):
            self.state.inventory_selected=int(action.split(':')[1]); self._use_selected_item()
        elif action.startswith('appearance:'):
            field=action.split(':')[1]; limit={'skin':4,'hair_style':4,'hair_color':5,'shirt':6,'pants':4}[field]
            self.custom_appearance[field]=(self.custom_appearance.get(field,0)+1)%limit

    def _travel(self,building_id):
        building=next(b for b in BUILDINGS if b['id']==building_id)
        door=self.world.door(building)
        self.state.player_x,self.state.player_y=door.x,door.y+24
        self._ensure_walkable(); self.scene='explore'; self._record_location()
        self._notify(self.t(building['label'])); self.save_manager.save(self.state,'auto')

    def _player_rect(self,x=None,y=None):
        return pygame.Rect(round((self.state.player_x if x is None else x)-8),round((self.state.player_y if y is None else y)-6),16,13)

    def _move(self,dx,dy):
        steps=max(1,math.ceil(max(abs(dx),abs(dy))/5))
        for _ in range(steps):
            if not self.world.collides(self._player_rect(x=self.state.player_x+dx/steps)): self.state.player_x+=dx/steps
            if not self.world.collides(self._player_rect(y=self.state.player_y+dy/steps)): self.state.player_y+=dy/steps

    def _update_explore(self,dt):
        self.state.play_seconds+=dt; self.state.time_minutes+=dt*1.5
        if self.state.time_minutes>=22*60:
            self.state.day+=1; self.state.time_minutes=7*60; self.state.energy=100
        factor={'easy':.06,'normal':.10,'hard':.18}.get(self.state.difficulty,.1)
        self.state.hunger=max(0,self.state.hunger-dt*factor)
        self.state.thirst=max(0,self.state.thirst-dt*factor*1.3)
        keys=pygame.key.get_pressed()
        direction=pygame.Vector2(float(keys[pygame.K_d] or keys[pygame.K_RIGHT])-float(keys[pygame.K_a] or keys[pygame.K_LEFT]),float(keys[pygame.K_s] or keys[pygame.K_DOWN])-float(keys[pygame.K_w] or keys[pygame.K_UP]))
        self.player_moving=direction.length_squared()>0
        if self.player_moving:
            direction=direction.normalize(); running=keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            speed=205 if running and self.state.energy>1 else 134
            if self.riding_bike: speed=275
            self._move(direction.x*speed*dt,direction.y*speed*dt)
            self.state.facing=('left' if direction.x<0 else 'right') if abs(direction.x)>abs(direction.y) else ('up' if direction.y<0 else 'down')
            self.state.energy=max(0,self.state.energy-dt*(1 if running else .02))
        else: self.state.energy=min(100,self.state.energy+dt*.4)
        self._record_location()
        if pygame.time.get_ticks()-self.last_autosave>45000:
            self.save_manager.save(self.state,'auto'); self.last_autosave=pygame.time.get_ticks()

    def _record_location(self):
        point=(self.state.player_x/TILE,self.state.player_y/TILE)
        complete=[]
        for zone in ZONES:
            if pygame.Rect(zone['rect']).collidepoint(point) and zone['id'] not in self.state.visited_zones:
                complete+=self.quests.record_visit(zone['id'])
        for b in BUILDINGS:
            if pygame.Rect(b['rect'].pixels()).inflate(150,150).collidepoint(self.state.player_x,self.state.player_y): self.state.discovered_landmarks.add(b['id'])
        self._completed(complete)

    def _nearby(self):
        player=pygame.Vector2(self.state.player_x,self.state.player_y)
        candidates=[(player.distance_to(tile_center(n['tile'])),'npc',n) for n in NPCS]
        candidates += [(player.distance_to(self.world.door(b)),'building',b) for b in BUILDINGS]
        candidates += [(player.distance_to(tile_center(s['tile'])),'shop',s) for s in SHOPS]
        distance,kind,value=min(candidates,key=lambda v:v[0])
        return (kind,value) if distance<65 else (None,None)

    def _interact(self):
        kind,item=self._nearby()
        if kind=='building':
            self.current_interior=item; self.room_position=pygame.Vector2(.5,.80); self.scene='interior'; self.riding_bike=False
        elif kind=='shop' or (kind=='npc' and item['id']=='vendor'):
            self.state.hunger=100; self.state.thirst=100; self.state.supplies={'water':3,'snack':2}
            self._notify(self.t('v5.served')); self.audio.play('select')
        elif kind=='npc':
            self.dialog_speaker=self.t(item['name'])
            completed=self.quests.record_talk(item['id'])
            qid,result=self.quests.activate_from_npc(item['id'])
            self.dialog_lines=[self.t(item['dialog'],name=self.state.player_name)]
            if result=='accepted': self.dialog_lines.append(self.t('dialog.accept'))
            self.scene='dialog'; self.audio.play('voice'); self._completed(completed)
        else: self._notify(self.t('v5.approach'))
        self.save_manager.save(self.state,'auto')

    def _completed(self,ids):
        if ids:
            self.audio.play('quest'); self._notify(self.t('v5.quest_done'))

    def _inventory_items(self):
        return [('map','v5.tool.map'),('notebook','v5.tool.notes'),('camera','v5.tool.camera'),('water','v5.tool.water'),('snack','v5.tool.meal'),('bike','v5.tool.bike')]

    def _use_selected_item(self): self._use_tool(self._inventory_items()[self.state.inventory_selected][0])

    def _use_tool(self,tool):
        if tool in ('map','notebook'): self.scene=tool
        elif tool=='bike': self.riding_bike=not self.riding_bike; self._notify(self.t('v5.bike_on' if self.riding_bike else 'v5.bike_off'))
        elif tool=='camera':
            player=pygame.Vector2(self.state.player_x,self.state.player_y)
            closest=min(BUILDINGS,key=lambda b:player.distance_to(pygame.Rect(b['rect'].pixels()).center))
            if player.distance_to(pygame.Rect(closest['rect'].pixels()).center)<600:
                self.state.photos.add(closest['id']); self._notify(self.t('v5.photo',name=self.t(closest['label']))); self.audio.play('photo')
                self.state.observations.add('photo:'+closest['id']); self.save_manager.save(self.state,'auto')
            else: self._notify(self.t('v5.camera_hint'))
        elif tool in ('water','snack'):
            if self.state.supplies[tool]<=0: self._notify(self.t('v5.empty_supply')); return
            self.state.supplies[tool]-=1
            if tool=='water': self.state.thirst=min(100,self.state.thirst+45)
            else: self.state.hunger=min(100,self.state.hunger+40)
            self._notify(self.t('v5.drank' if tool=='water' else 'v5.ate'))

    def _room_objects(self):
        b=self.current_interior
        if b and b['id'] in DORMS:
            return [('bed',(.32,.39)),('desk',(.32,.66)),('notice',(.5,.23)),('water',(.69,.68))]
        if b and 'library' in b['id']: return [('books',(.28,.43)),('terminal',(.5,.23)),('archive',(.72,.65))]
        if b and b.get('style') in ('dining','activity'): return [('counter',(.5,.27)),('water',(.71,.62)),('notice',(.30,.50))]
        return [('terminal',(.5,.25)),('exhibit',(.29,.5)),('notice',(.70,.65))]

    def _update_interior(self,dt):
        self.state.play_seconds+=dt
        keys=pygame.key.get_pressed()
        direction=pygame.Vector2(float(keys[pygame.K_d] or keys[pygame.K_RIGHT])-float(keys[pygame.K_a] or keys[pygame.K_LEFT]),float(keys[pygame.K_s] or keys[pygame.K_DOWN])-float(keys[pygame.K_w] or keys[pygame.K_UP]))
        self.player_moving=direction.length_squared()>0
        if not self.player_moving: return
        direction=direction.normalize()
        self.room_position+=direction*dt*.20
        self.room_position.x=max(.35,min(.65,self.room_position.x)); self.room_position.y=max(.30,min(.91,self.room_position.y))
        self.state.facing=('left' if direction.x<0 else 'right') if abs(direction.x)>abs(direction.y) else ('up' if direction.y<0 else 'down')

    def _interact_interior(self):
        if self.room_position.y>.85: self._leave_special_area(); return
        distance,kind=min((self.room_position.distance_to(pos),kind) for kind,pos in self._room_objects())
        if distance>.23: self._notify(self.t('v5.room_hint')); return
        building=self.current_interior
        self.state.observations.add(building['id']+':'+kind)
        if kind=='bed': self.state.energy=100; self._notify(self.t('v5.rested'))
        elif kind=='water': self.state.thirst=100; self.state.supplies['water']=3; self._notify(self.t('v5.water_filled'))
        elif kind=='counter': self.state.hunger=100; self.state.supplies['snack']=2; self._notify(self.t('v5.served'))
        else: self._notify(self.t('v5.observe.'+kind))
        self.audio.play('select'); self.save_manager.save(self.state,'auto')

    def _leave_special_area(self): self.current_interior=None; self.scene='explore'; self.player_moving=False

    def _notify(self,text): self.notification=text; self.notification_until=pygame.time.get_ticks()+3800

    def _button(self,rect,label,action,mouse,enabled=True,primary=False):
        button=Button(pygame.Rect(rect),label,action,enabled,primary); button.draw(self.canvas,self.fonts,mouse); self.buttons.append(button)

    def _draw(self,mouse):
        self.buttons=[]; self.canvas.fill(PAPER)
        if self.scene=='title': self._draw_title(mouse)
        elif self.scene=='customize': self._draw_customize(mouse)
        elif self.scene=='interior': self._draw_interior(mouse)
        elif self.scene=='settings': self._draw_settings(mouse)
        else:
            self._draw_explore(mouse)
            if self.scene=='dialog': self._draw_dialog()
            elif self.scene=='map': self._draw_map(mouse)
            elif self.scene=='notebook': self._draw_notebook(mouse)
            elif self.scene=='guide': self._draw_guide(mouse)
            elif self.scene=='pause': self._draw_pause(mouse)
            elif self.scene=='save_menu': self._draw_slots(mouse)

    def _draw_title(self,mouse):
        ren=next(b for b in BUILDINGS if b['id']=='ren_hall'); door=self.world.door(ren)
        camera=self.world.camera_for(door.x,door.y)
        self.canvas.blit(self.world.ground,(0,0),camera)
        for x,y,tree in self.world.trees:
            if camera.inflate(200,200).collidepoint(x,y): self.canvas.blit(tree,(x-camera.x-tree.get_width()/2,y-camera.y-tree.get_height()+12))
        wash=pygame.Surface(WINDOW_SIZE,pygame.SRCALPHA); wash.fill((238,237,222,110)); self.canvas.blit(wash,(0,0))
        panel(self.canvas,(70,75,510,570),alpha=244)
        self.fonts.draw(self.canvas,self.t('game.title'),(110,115),54,GREEN,True)
        self.fonts.draw(self.canvas,self.t('v5.subtitle'),(113,190),22,MUTED)
        labels=[('menu.continue','continue',self.save_manager.newest_available() is not None),('menu.new_game','new',True),('v5.dorm_tour','dorm_tour',True),('menu.settings','settings',True),('menu.quit','quit',True)]
        for i,(key,action,enabled) in enumerate(labels): self._button((110,258+i*63,430,48),self.t(key),action,mouse,enabled,i==0)
        self.fonts.draw(self.canvas,self.t('game.disclaimer'),(1240,690),14,INK,False,'bottomright')

    def _draw_customize(self,mouse):
        self.fonts.draw(self.canvas,self.t('custom.title'),(90,55),38,GREEN,True)
        panel(self.canvas,(90,130,360,460),(226,230,212))
        self.world.characters.draw(self.canvas,(270,440),'down',True,self.custom_appearance,pygame.time.get_ticks(),3.8)
        self.fonts.draw(self.canvas,self.custom_name or self.t('v5.name_hint'),(270,530),24,GREEN,True,'center')
        self.fonts.draw(self.canvas,self.t('custom.name'),(515,150),22)
        panel(self.canvas,(515,188,590,60)); self.fonts.draw(self.canvas,self.custom_name+('│' if pygame.time.get_ticks()//500%2 else ''),(535,204),26)
        for i,key in enumerate(('skin','hair_style','hair_color','shirt','pants')):
            self._button((515+i%2*305,285+i//2*74,280,52),self.t('custom.'+key),'appearance:'+key,mouse)
        self._button((515,535,300,55),self.t('custom.start'),'custom_start',mouse,True,True)
        self._button((845,535,260,55),self.t('menu.back'),'title',mouse)

    def _draw_explore(self,mouse):
        camera=self.world.camera_for(self.state.player_x,self.state.player_y)
        self.world.draw_view(self.canvas,camera,NPCS,self.state,self.player_moving,pygame.time.get_ticks())
        if self.riding_bike:
            x,y=self.state.player_x-camera.x,self.state.player_y-camera.y
            for dx in (-15,15): pygame.draw.circle(self.canvas,(64,78,71),(round(x+dx),round(y-4)),11,2)
            pygame.draw.aalines(self.canvas,GREEN,False,[(x-15,y-4),(x,y-20),(x+15,y-4),(x-3,y-4),(x-15,y-4)])
        hour=self.state.time_minutes/60
        if hour>=19:
            dusk=pygame.Surface(WINDOW_SIZE,pygame.SRCALPHA); dusk.fill((26,47,63,50)); self.canvas.blit(dusk,(0,0))
        self._draw_hud(mouse)

    def _draw_hud(self,mouse):
        panel(self.canvas,(22,20,290,99),alpha=237)
        self.fonts.draw(self.canvas,self.state.player_name,(40,31),21,GREEN,True)
        for i,(key,value,color) in enumerate([('v5.hunger',self.state.hunger,(163,119,94)),('v5.thirst',self.state.thirst,(104,151,162)),('v5.energy',self.state.energy,(142,156,112))]):
            y=61+i*16; self.fonts.draw(self.canvas,self.t(key),(40,y-3),13,MUTED)
            pygame.draw.rect(self.canvas,(220,223,209),(105,y,180,7),border_radius=3)
            pygame.draw.rect(self.canvas,color,(105,y,round(180*value/100),7),border_radius=3)
        panel(self.canvas,(1092,20,164,78),alpha=235)
        hour,minute=divmod(int(self.state.time_minutes),60)
        self.fonts.draw(self.canvas,f'D{self.state.day}  {hour:02d}:{minute:02d}',(1174,44),24,GREEN,True,'center')
        self.fonts.draw(self.canvas,self.t('v5.weather'),(1174,76),14,MUTED,False,'center')
        kind,item=self._nearby()
        hint='E · '+self.t(item['name'] if kind=='npc' else item['label']) if kind in ('npc','building') else self.t('v5.controls')
        if kind=='shop': hint=self.t('v5.shop_hint')
        width=min(1000,self.fonts.get(17).size(hint)[0]+36)
        panel(self.canvas,((1280-width)//2,583,width,33),alpha=235)
        self.fonts.draw(self.canvas,hint,(640,599),17,GREEN,False,'center')
        self._draw_inventory_bar(mouse)
        self._draw_notice()

    def _draw_inventory_bar(self,mouse):
        panel(self.canvas,(268,634,744,66),alpha=247)
        self.inventory_rects=[]
        for i,(tool,label) in enumerate(self._inventory_items()):
            rect=pygame.Rect(278+i*122,644,114,46); self.inventory_rects.append(rect)
            count=f' {self.state.supplies[tool]}' if tool in ('water','snack') else ''
            self._button(rect,f'{i+1}  {self.t(label)}{count}','tool:'+str(i),mouse,True,i==self.state.inventory_selected)

    def _draw_notice(self):
        if self.notification and pygame.time.get_ticks()<self.notification_until:
            width=min(1100,self.fonts.get(19).size(self.notification)[0]+48)
            panel(self.canvas,((1280-width)//2,526,width,43),(235,237,222),250)
            self.fonts.draw(self.canvas,self.notification,(640,547),19,GREEN,True,'center')

    def _dim(self):
        layer=pygame.Surface(WINDOW_SIZE,pygame.SRCALPHA); layer.fill((24,43,35,105)); self.canvas.blit(layer,(0,0))

    def _draw_dialog(self):
        self._dim(); panel(self.canvas,(100,470,1080,210))
        self.fonts.draw(self.canvas,self.dialog_speaker,(132,492),25,GREEN,True)
        for i,line in enumerate(self.fonts.wrapped(' '.join(self.dialog_lines),22,1010)[:4]): self.fonts.draw(self.canvas,line,(132,534+i*29),22)
        self.fonts.draw(self.canvas,self.t('dialog.continue'),(1145,660),16,MUTED,False,'bottomright')

    def _draw_map(self,mouse):
        self._dim(); panel(self.canvas,(45,32,1190,655))
        self.fonts.draw(self.canvas,self.t('panel.map'),(75,55),30,GREEN,True)
        self.map_rect=pygame.Rect(76,113,760,532)
        self.canvas.blit(pygame.transform.smoothscale(self.world.minimap,self.map_rect.size),self.map_rect)
        sx,sy=self.map_rect.width/WORLD_WIDTH,self.map_rect.height/WORLD_HEIGHT
        for b in BUILDINGS:
            pos=self.world.door(b); point=(round(self.map_rect.x+pos.x*sx),round(self.map_rect.y+pos.y*sy))
            pygame.draw.circle(self.canvas,GREEN,point,4)
        pygame.draw.circle(self.canvas,(163,84,58),(round(self.map_rect.x+self.state.player_x*sx),round(self.map_rect.y+self.state.player_y*sy)),6)
        self.fonts.draw(self.canvas,self.t('v5.map_hint'),(865,115),18,GREEN,True)
        for i,key in enumerate(DORMS): self._button((865,175+i*64,330,48),self.t('landmark.'+key),'travel:'+key,mouse)
        self._button((865,455,330,48),self.t('landmark.main_library'),'travel:main_library',mouse)
        self._button((865,515,330,48),self.t('landmark.dining_hall'),'travel:dining_hall',mouse)
        self._button((1055,61,140,38),self.t('menu.back'),'close',mouse)

    def _map_click(self,mouse):
        if not self.map_rect.collidepoint(mouse): return
        x=(mouse[0]-self.map_rect.x)/self.map_rect.width*WORLD_WIDTH
        y=(mouse[1]-self.map_rect.y)/self.map_rect.height*WORLD_HEIGHT
        building=min(BUILDINGS,key=lambda b:self.world.door(b).distance_to((x,y)))
        if self.world.door(building).distance_to((x,y))<220: self._travel(building['id'])

    def _draw_notebook(self,mouse):
        self._dim(); panel(self.canvas,(60,40,1160,640))
        self.fonts.draw(self.canvas,self.t('panel.quests'),(90,65),30,GREEN,True)
        self.fonts.draw(self.canvas,self.t('v5.progress',value=self.quests.completion_percent()),(900,76),19,MUTED)
        for i,q in enumerate(QUESTS):
            x,y=90+i%2*555,130+i//2*119
            panel(self.canvas,(x,y,530,100),(238,239,224))
            value=self.state.quest_states[q['id']]; current,total=self.quests.objective_progress(q)
            self.fonts.draw(self.canvas,self.t(q['title']),(x+16,y+12),21,GREEN,True)
            for j,line in enumerate(self.fonts.wrapped(self.t(q['desc']),16,465)[:2]): self.fonts.draw(self.canvas,line,(x+16,y+43+j*19),16,MUTED)
            self.fonts.draw(self.canvas,('✓' if value['status']=='completed' else f'{current}/{total}'),(x+505,y+72),19,GREEN,True,'topright')
        self.fonts.draw(self.canvas,self.t('v5.observations',photos=len(self.state.photos),notes=len(self.state.observations)),(90,635),17,MUTED)
        self._button((1060,65,125,39),self.t('menu.back'),'close',mouse)

    def _draw_guide(self,mouse):
        self._dim(); panel(self.canvas,(55,35,1170,650))
        self.fonts.draw(self.canvas,self.t('v5.dorm_guide'),(85,60),30,GREEN,True)
        for i,key in enumerate(DORMS): self._button((85+i*275,115,255,44),self.t('landmark.'+key),'dorm:'+key,mouse,True,key==self.selected_dorm)
        art=self.world.facades[self.selected_dorm]
        ratio=min(700/art.get_width(),400/art.get_height())
        art=pygame.transform.smoothscale(art,(round(art.get_width()*ratio),round(art.get_height()*ratio)))
        self.canvas.blit(art,art.get_rect(midbottom=(450,600)))
        self.fonts.draw(self.canvas,self.t('landmark.'+self.selected_dorm),(845,200),28,GREEN,True)
        for i,line in enumerate(self.fonts.wrapped(self.t('v5.dorm.'+self.selected_dorm),20,310)): self.fonts.draw(self.canvas,line,(845,255+i*31),20)
        self.fonts.draw(self.canvas,self.t('v5.reference_note'),(845,480),15,MUTED)
        self._button((845,540,310,48),self.t('v5.go_here'),'travel:'+self.selected_dorm,mouse,True,True)
        self._button((1040,62,145,38),self.t('menu.back'),'close',mouse)

    def _draw_interior(self,mouse):
        b=self.current_interior or BUILDINGS[0]
        self.canvas.fill((224,225,209))
        self.canvas.blit(self.world.room_image(b,self.room_rect.size),self.room_rect)
        panel(self.canvas,(20,75,285,435),alpha=247)
        self.fonts.draw(self.canvas,self.t(b['label']),(40,100),24,GREEN,True)
        description=self.t('v5.dorm.'+b['id']) if b['id'] in DORMS else self.t('v5.indoor_text')
        for i,line in enumerate(self.fonts.wrapped(description,18,245)[:8]): self.fonts.draw(self.canvas,line,(40,158+i*29),18,MUTED)
        self.fonts.draw(self.canvas,self.t('v5.room_controls'),(40,400),17,GREEN)
        self._button((40,445,245,43),self.t('v5.leave'),'leave',mouse)
        # Side panel indicates nearby activities, not collectible items.
        panel(self.canvas,(975,100,280,380),alpha=246)
        self.fonts.draw(self.canvas,self.t('v5.room_activities'),(995,125),22,GREEN,True)
        for i,(kind,pos) in enumerate(self._room_objects()):
            near=self.room_position.distance_to(pos)<.23
            self.fonts.draw(self.canvas,('E · ' if near else '· ')+self.t('interior.object.'+kind),(995,185+i*54),18,GREEN if near else MUTED,near)
            if near:
                x=self.room_rect.x+pos[0]*620; y=self.room_rect.y+pos[1]*620
                pygame.draw.circle(self.canvas,(143,151,114),(round(x),round(y)),9,1)
        x=self.room_rect.x+self.room_position.x*620; y=self.room_rect.y+self.room_position.y*620
        self.world.characters.draw(self.canvas,(x,y),self.state.facing,self.player_moving,self.state.appearance,pygame.time.get_ticks(),1.25)
        self._draw_notice()

    def _draw_pause(self,mouse):
        self._dim(); panel(self.canvas,(415,110,450,505))
        self.fonts.draw(self.canvas,self.t('menu.paused'),(640,152),32,GREEN,True,'center')
        for i,(key,action) in enumerate([('menu.resume','resume'),('menu.save','save_menu'),('menu.settings','settings'),('menu.title','title'),('menu.quit','quit')]): self._button((455,210+i*69,370,50),self.t(key),action,mouse,True,i==0)

    def _draw_slots(self,mouse):
        self._dim(); panel(self.canvas,(360,110,560,490))
        self.fonts.draw(self.canvas,self.t('menu.save'),(400,145),30,GREEN,True)
        for i in range(3): self._button((400,220+i*86,480,59),self.t('menu.slot',slot=i+1),'slot:'+str(i+1),mouse)
        self._button((400,510,480,45),self.t('menu.back'),'back',mouse)

    def _draw_settings(self,mouse):
        self.canvas.fill((226,230,214)); panel(self.canvas,(300,100,680,530))
        self.fonts.draw(self.canvas,self.t('menu.settings'),(640,150),36,GREEN,True,'center')
        self._button((355,240,570,60),self.t('v5.language')+'  '+('繁體中文' if self.localizer.language=='zh_TW' else 'English'),'language',mouse)
        self._button((355,330,570,60),self.t('v5.fullscreen'),'fullscreen',mouse)
        self._button((355,480,570,60),self.t('menu.back'),'back',mouse)
