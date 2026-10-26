"""Native-resolution, matte hand-painted 2D campus renderer. No 3D scene."""
from __future__ import annotations
import math
import random
import pygame
from .constants import ROOT, TILE, WORLD_WIDTH, WORLD_HEIGHT, INTERNAL_WIDTH, INTERNAL_HEIGHT
from .content import BUILDINGS, DORMS, ROADS, WATERS, SPORTS_FIELDS, MAIN_GATE_TILE, NPCS, tile_center

ASSETS = ROOT / "assets" / "painted"
INK = (48, 58, 54)
PAPER = (245, 242, 230)
SAGE = (98, 125, 111)
HAIR = [(56,45,39),(34,37,38),(115,78,51),(91,57,69),(180,149,101)]
SHIRTS = [(89,121,117),(114,101,126),(149,100,83),(87,113,143),(170,142,93),(104,131,100)]
SKIN = [(235,204,174),(213,179,145),(179,139,105),(115,83,65)]

def load_image(name):
    return pygame.image.load(str(ASSETS / name)).convert_alpha()

def crop_cell(sheet, col, row, columns=2, rows=2):
    w,h=sheet.get_width()//columns,sheet.get_height()//rows
    cell=sheet.subsurface((col*w,row*h,w,h)).copy()
    return cell.subsurface(cell.get_bounding_rect(min_alpha=80)).copy()

class Characters:
    def __init__(self):
        sheet=load_image("student-walk-v5.png")
        self.frames=[]; self.cache={}
        for row in range(4):
            self.frames.append([])
            for col in range(4):
                cell=crop_cell(sheet,col,row,4,4)
                h=64; w=max(18,round(cell.get_width()/cell.get_height()*h))
                self.frames[row].append(pygame.transform.smoothscale(cell,(w,h)))

    def sprite(self,facing,frame,appearance):
        row={"down":0,"left":1,"right":2,"up":3}.get(facing,0)
        key=(row,frame,tuple(sorted(appearance.items())))
        if key not in self.cache:
            sprite=self.frames[row][frame].copy()
            # The authored left-row poses face right; reflect them consistently.
            if facing=="left": sprite=pygame.transform.flip(sprite,True,False)
            shirt=SHIRTS[appearance.get("shirt",0)%6]
            hair=HAIR[appearance.get("hair_color",0)%5]
            skin=SKIN[appearance.get("skin",1)%4]
            for y in range(sprite.get_height()):
                for x in range(sprite.get_width()):
                    r,g,b,a=sprite.get_at((x,y))
                    if a<80: continue
                    target=None
                    if y<12 and max(r,g,b)<135: target=hair
                    elif 13<y<39 and g>r*1.03 and b>r and max(r,g,b)<175: target=shirt
                    elif y<37 and r>145 and r>g*1.08 and g>b*1.08: target=skin
                    if target:
                        light=max(0.45,min(1.3,(r+g+b)/330))
                        sprite.set_at((x,y),(*[min(255,round(v*light)) for v in target],a))
            style=appearance.get("hair_style",0)%4
            if style in (1,3): pygame.draw.ellipse(sprite,hair,(sprite.get_width()//2+4,4,4,10))
            if style==2: pygame.draw.ellipse(sprite,hair,(sprite.get_width()//2-5,0,9,6))
            self.cache[key]=sprite
        return self.cache[key]

    def draw(self,target,position,facing,moving,appearance,tick,scale=1):
        sprite=self.sprite(facing,int(tick//150)%4 if moving else 0,appearance)
        if scale!=1: sprite=pygame.transform.smoothscale(sprite,(round(sprite.get_width()*scale),round(sprite.get_height()*scale)))
        x,y=map(round,position)
        shadow=pygame.Surface((36,10),pygame.SRCALPHA)
        pygame.draw.ellipse(shadow,(35,49,40,42),shadow.get_rect())
        target.blit(shadow,(x-18,y-5))
        target.blit(sprite,(x-sprite.get_width()//2,y-sprite.get_height()))

class PaperWorld:
    def __init__(self):
        self.characters=Characters()
        self.collision_rects=[pygame.Rect(v.pixels()).inflate(-10,-10) for v in WATERS]
        self.collision_rects += [pygame.Rect(b["rect"].pixels()).inflate(4,4) for b in BUILDINGS]
        self.facades={}
        atlas=load_image("dorm-facades-v5.png")
        # Authored cutouts use their actual gutters, avoiding clipping towers.
        w,h=atlas.get_size()
        cuts={"shi_hall":(.55,.065,.445,.435),"li_hall":(0,.52,.60,.445),"yi_hall":(.625,.52,.37,.445)}
        for key,(x,y,cw,ch) in cuts.items():
            cell=atlas.subsurface(pygame.Rect(round(x*w),round(y*h),round(cw*w),round(ch*h))).copy()
            self.facades[key]=cell.subsurface(cell.get_bounding_rect(min_alpha=90)).copy()
        ren=load_image("ren-facade-v5.png")
        ren=ren.subsurface(ren.get_bounding_rect(min_alpha=90)).copy()
        # Correct the generated three-row wing to the four visible storeys in
        # the official facade reference, by repeating its authored window bay.
        band_top,band_height=round(ren.get_height()*.44),round(ren.get_height()*.245)
        four_storeys=pygame.Surface((ren.get_width(),ren.get_height()+band_height),pygame.SRCALPHA)
        four_storeys.blit(ren,(0,0),(0,0,ren.get_width(),band_top))
        four_storeys.blit(ren,(0,band_top),(0,band_top,ren.get_width(),band_height))
        four_storeys.blit(ren,(0,band_top+band_height),(0,band_top,ren.get_width(),ren.get_height()-band_top))
        self.facades["ren_hall"]=four_storeys
        tree_sheet=load_image("trees-v5.png")
        self.tree_images=[crop_cell(tree_sheet,i%2,i//2) for i in range(4)]
        room_sheet=load_image("room-plans-v5.png")
        self.rooms=[room_sheet.subsurface((i%2*room_sheet.get_width()//2,i//2*room_sheet.get_height()//2,room_sheet.get_width()//2,room_sheet.get_height()//2)).copy() for i in range(4)]
        materials=load_image("ground-materials-v5.png")
        self.materials=[pygame.transform.smoothscale(crop_cell(materials,i%2,i//2),(256,256)) for i in range(4)]
        self.ground=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT))
        self.trees=[]
        self._build()

    def _build(self):
        rng=random.Random(10426)
        # High-resolution hand-painted material swatches, not pixel-art tiles.
        for y in range(0,WORLD_HEIGHT,256):
            for x in range(0,WORLD_WIDTH,256):
                self.ground.blit(pygame.transform.rotate(self.materials[0],rng.choice((0,90,180,270))),(x,y))
        for road in ROADS:
            rect=pygame.Rect(road.pixels())
            pygame.draw.rect(self.ground,(139,153,127),rect.inflate(8,8),border_radius=8)
            pygame.draw.rect(self.ground,(216,210,190),rect,border_radius=7)
            self.ground.set_clip(rect)
            for py in range(rect.top//256*256,rect.bottom,256):
                for px in range(rect.left//256*256,rect.right,256): self.ground.blit(self.materials[1],(px,py))
            self.ground.set_clip(None)
        for water in WATERS:
            rect=pygame.Rect(water.pixels())
            pygame.draw.rect(self.ground,(114,141,125),rect.inflate(20,20),border_radius=66)
            pygame.draw.rect(self.ground,(105,149,153),rect,border_radius=56)
            self.ground.set_clip(rect.inflate(-44,-44))
            for py in range(rect.top//256*256,rect.bottom,256):
                for px in range(rect.left//256*256,rect.right,256): self.ground.blit(self.materials[3],(px,py))
            self.ground.set_clip(None)
            for _ in range(rect.width*rect.height//500):
                x,y=rng.randrange(rect.left+40,rect.right-40),rng.randrange(rect.top+40,rect.bottom-40)
                pygame.draw.line(self.ground,(126,167,168),(x,y),(x+rng.randrange(4,18),y),1)
            for x in range(rect.left+40,rect.right-20,48):
                pygame.draw.ellipse(self.ground,(105,134,91),(x,rect.bottom-13,12,6))
        for field in SPORTS_FIELDS:
            rect=pygame.Rect(field.pixels())
            pygame.draw.rect(self.ground,(167,139,112),rect.inflate(10,10),border_radius=12)
            pygame.draw.rect(self.ground,(142,164,123),rect)
            pygame.draw.rect(self.ground,(237,232,211),rect.inflate(-20,-20),2)
            pygame.draw.line(self.ground,(237,232,211),(rect.centerx,rect.top+10),(rect.centerx,rect.bottom-10),2)
            pygame.draw.circle(self.ground,(237,232,211),rect.center,35,2)
        for building in BUILDINGS: self._building(building,rng)
        forbidden=self.collision_rects+[pygame.Rect(v.pixels()).inflate(28,28) for v in ROADS]
        forbidden += [pygame.Rect(v.pixels()).inflate(12,12) for v in SPORTS_FIELDS]
        forbidden += [pygame.Rect(round(self.door(b).x)-60,round(self.door(b).y)-15,120,120) for b in BUILDINGS]
        forbidden += [pygame.Rect(*tile_center(n['tile']),1,1).inflate(75,75) for n in NPCS]
        for i in range(700):
            x,y=rng.randrange(40,WORLD_WIDTH-40),rng.randrange(60,WORLD_HEIGHT-30)
            if any(r.colliderect(pygame.Rect(x-14,y-14,28,28)) for r in forbidden): continue
            base=self.tree_images[i%4]
            h=rng.randrange(95,150); w=round(base.get_width()/base.get_height()*h)
            image=pygame.transform.smoothscale(base,(w,h))
            self.trees.append((x,y,image))
        gx,gy=tile_center(MAIN_GATE_TILE)
        pygame.draw.rect(self.ground,(203,195,171),(gx-86,gy-40,172,10))
        for x in (gx-80,gx+70): pygame.draw.rect(self.ground,(160,133,108),(x,gy-30,10,45))
        self.minimap=pygame.transform.smoothscale(self.ground,(640,448))
        # Include symbolic foliage on the map without perspective or artwork UI.
        for x,y,_ in self.trees: pygame.draw.circle(self.minimap,(106,133,104),(round(x/WORLD_WIDTH*640),round(y/WORLD_HEIGHT*448)),2)

    def _building(self,b,rng):
        rect=pygame.Rect(b["rect"].pixels())
        pygame.draw.rect(self.ground,(204,200,179),(rect.left-3,rect.bottom-3,rect.width+6,12),border_radius=3)
        if b["id"] in self.facades:
            original=self.facades[b["id"]]
            self.ground.blit(pygame.transform.smoothscale(original,rect.size),rect)
        else:
            style=b.get("style","")
            wall=(216,210,191) if b["color"]=="purple" else (196,166,139)
            pygame.draw.rect(self.ground,wall,rect)
            pygame.draw.rect(self.ground,(122,118,104),rect,1)
            pygame.draw.line(self.ground,(158,145,123),(rect.left,rect.top+7),(rect.right,rect.top+7),5)
            for y in range(rect.top+20,rect.bottom-22,38):
                for x in range(rect.left+16,rect.right-18,35):
                    pygame.draw.rect(self.ground,(119,151,151),(x,y,23,22))
                    pygame.draw.rect(self.ground,(231,223,200),(x,y,23,22),2)
                    pygame.draw.line(self.ground,(202,211,196),(x+11,y+2),(x+11,y+20),1)
            if style=="macronix":
                glass=pygame.Rect(rect.left+10,rect.top+12,rect.width//3,rect.height-25)
                pygame.draw.rect(self.ground,(107,151,157),glass)
                for x in range(glass.left+16,glass.right,18): pygame.draw.line(self.ground,(205,214,202),(x,glass.top),(x,glass.bottom),2)
            for _ in range(rect.width*rect.height//80):
                x,y=rng.randrange(rect.left,rect.right),rng.randrange(rect.top,rect.bottom)
                if self.ground.get_at((x,y))[:3]==wall:
                    color=tuple(max(0,v+rng.randrange(-9,6)) for v in wall)
                    self.ground.set_at((x,y),color)
        door=self.door(b)
        pygame.draw.rect(self.ground,(220,215,194),(door.x-27,rect.bottom-3,54,13))
        pygame.draw.line(self.ground,(174,171,153),(door.x-27,rect.bottom+4),(door.x+27,rect.bottom+4),1)
        # Connect each entrance to the closest pedestrian artery.
        closest=min((pygame.Rect(r.pixels()) for r in ROADS),key=lambda r:pygame.Vector2(max(r.left,min(r.right,door.x)),max(r.top,min(r.bottom,door.y))).distance_to(door))
        destination=pygame.Vector2(max(closest.left+8,min(closest.right-8,door.x)),max(closest.top+8,min(closest.bottom-8,door.y)))
        if destination.distance_to(door)<210:
            pygame.draw.line(self.ground,(165,167,146),door,destination,28)
            pygame.draw.line(self.ground,(190,184,164),door,destination,23)

    def door(self,b):
        rect=pygame.Rect(b["rect"].pixels())
        return pygame.Vector2(rect.centerx,rect.bottom+17)

    def collides(self,rect):
        return rect.left<10 or rect.top<10 or rect.right>WORLD_WIDTH-10 or rect.bottom>WORLD_HEIGHT-10 or any(rect.colliderect(r) for r in self.collision_rects)

    def camera_for(self,x,y):
        return pygame.Rect(max(0,min(WORLD_WIDTH-INTERNAL_WIDTH,round(x-INTERNAL_WIDTH/2))),max(0,min(WORLD_HEIGHT-INTERNAL_HEIGHT,round(y-INTERNAL_HEIGHT/2))),INTERNAL_WIDTH,INTERNAL_HEIGHT)

    def draw_view(self,target,camera,actors,state,moving,tick):
        target.blit(self.ground,(0,0),camera)
        layers=[]
        for x,y,image in self.trees:
            if camera.inflate(200,200).collidepoint(x,y): layers.append((y,"tree",(x,y,image)))
        for actor in actors:
            x,y=tile_center(actor["tile"])
            if camera.inflate(100,100).collidepoint(x,y): layers.append((y,"npc",actor))
        layers.append((state.player_y,"player",None))
        for _,kind,value in sorted(layers,key=lambda v:v[0]):
            if kind=="tree":
                x,y,image=value
                target.blit(image,(x-camera.x-image.get_width()/2,y-camera.y-image.get_height()+12))
            else:
                if kind=="player": x,y=state.player_x,state.player_y; appearance=state.appearance; facing=state.facing
                else:
                    x,y=tile_center(value["tile"]); n=sum(map(ord,value["id"]))
                    appearance={"shirt":n%6,"hair_color":n%5,"skin":n%4,"hair_style":n%4}; facing="down"
                self.characters.draw(target,(x-camera.x,y-camera.y),facing,moving if kind=="player" else False,appearance,tick)
        # Sparse restrained ripple motion, not floating pickup sparkles.
        for spec in WATERS:
            water=pygame.Rect(spec.pixels()).inflate(-70,-70)
            if not water.colliderect(camera): continue
            for i in range(10):
                x=water.left+(i*83+tick//120)%max(1,water.width)
                y=water.top+(i*67)%max(1,water.height)
                pygame.draw.aaline(target,(153,183,177),(x-camera.x,y-camera.y),(x-camera.x+12,y-camera.y))

    def room_image(self,building,size):
        style=building.get("style","")
        index=0 if building["id"] in DORMS else 1 if "library" in building["id"] else 2 if style in ("dining","activity") else 3
        return pygame.transform.smoothscale(self.rooms[index],size)
