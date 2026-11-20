"""Native-resolution, matte hand-painted 2D campus renderer. No 3D scene."""
from __future__ import annotations
import math
import random
import pygame
from .constants import ROOT, TILE, WORLD_WIDTH, WORLD_HEIGHT, INTERNAL_WIDTH, INTERNAL_HEIGHT
from .content import BUILDINGS, DORMS, ARCHITECTURE, LANDSCAPES, SCENERY_POINTS, ROADS, WATERS, ISLANDS, WALKWAYS, LAKE_FEATURES, SPORTS_FIELDS, MAIN_GATE_TILE, NPCS, tile_center
from .geometry import pixel_points, smooth_path, smooth_polygon, stroke, distance_to_path
from .architecture import tsinghua_lab, life_science_2
from .character_art import figure

ASSETS = ROOT / "assets" / "painted"
INK = (48, 58, 54)
PAPER = (245, 242, 230)
SAGE = (98, 125, 111)
def load_image(name):
    return pygame.image.load(str(ASSETS / name)).convert_alpha()

def crop_cell(sheet, col, row, columns=2, rows=2):
    w, h = sheet.get_width() // columns, sheet.get_height() // rows
    cell = sheet.subsurface((col*w, row*h, w, h)).copy()
    return cell.subsurface(cell.get_bounding_rect(min_alpha=80)).copy()


class Characters:
    def __init__(self):
        self.cache = {}
        self.zombie_frames = {}
        self.shadow = pygame.Surface((40, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (27, 35, 32, 70), self.shadow.get_rect())
        bike_sheet=load_image("cyclists_spaced(1).png")
        frame_width=bike_sheet.get_width()//5
        frame_height=bike_sheet.get_height()//2
        self.bike_right=[]; self.bike_left=[]
        for col in range(5):
            for row,frames in ((0,self.bike_right),(1,self.bike_left)):
                cell=bike_sheet.subsurface((col*frame_width,row*frame_height,frame_width,frame_height)).copy()
                cell=cell.subsurface(cell.get_bounding_rect(min_alpha=80)).copy()
                frames.append(pygame.transform.smoothscale(cell,(68,74)))

    def sprite(self, facing, frame, appearance, *, preview=False):
        key = (facing, frame, preview, tuple(sorted(appearance.items())))
        if key not in self.cache:
            source = figure(facing, frame, appearance)
            size = (135, 203) if preview else (45, 68)
            self.cache[key] = pygame.transform.smoothscale(source, size)
        return self.cache[key]

    def draw(self, target, position, facing, moving, appearance, tick, scale=1, *, running=False, stride=None):
        cadence = 73 if running else 106
        motion = int(stride / 7) if stride is not None else tick // cadence
        frame = 1 + motion % 8 if moving else 0
        sprite = self.sprite(facing, frame, appearance)
        if scale != 1:
            sprite = pygame.transform.smoothscale(sprite, (round(sprite.get_width()*scale), round(sprite.get_height()*scale)))
        x, y = map(round, position)
        target.blit(self.shadow, self.shadow.get_rect(center=(x, y)))
        target.blit(sprite, sprite.get_rect(midbottom=(x, y)))

    def draw_bike(self, target, position, facing, moving, tick, appearance=None):
        if appearance is None:
            frames = self.bike_right if facing == "right" else self.bike_left
            sprite = frames[tick // 150 % len(frames) if moving else 0]
            target.blit(sprite, sprite.get_rect(midbottom=position))
            return
        x, y = map(round, position)
        direction = 1 if facing == "right" else -1
        rear, front = (x-21*direction, y-13), (x+23*direction, y-13)
        crank, saddle = (x+1*direction, y-12), (x-8*direction, y-31)
        handle = (x+18*direction, y-35)
        for wheel in (rear, front):
            pygame.draw.circle(target, (34, 44, 42), wheel, 12, 3)
            pygame.draw.circle(target, (115, 130, 121), wheel, 9, 1)
            angle = tick * .012 if moving else .3
            for phase in (angle, angle + math.pi / 2):
                dx, dy = round(math.cos(phase) * 8), round(math.sin(phase) * 8)
                pygame.draw.aaline(target, (117, 134, 127),
                                   (wheel[0]-dx, wheel[1]-dy), (wheel[0]+dx, wheel[1]+dy))
        pygame.draw.lines(target, (146, 106, 69), False, (rear, saddle, crank, rear), 3)
        pygame.draw.lines(target, (146, 106, 69), False, (crank, handle, front), 3)
        sprite = self.sprite(facing, tick // 145 % 4 if moving else 0, appearance)
        rider = pygame.transform.smoothscale(sprite, (sprite.get_width(), 49))
        target.blit(rider, rider.get_rect(midbottom=(x-2*direction, y-17)))
        pygame.draw.line(target, (42, 57, 53), handle, (handle[0]+6*direction, handle[1]), 3)

    def zombie_sprite(self, variant, facing, frame, windup):
        proportions = {
            "wanderer": (.91, 1.02, (121, 137, 105), 1, 1),
            "hunter": (1.12, 1.06, (152, 106, 83), 2, 1),
            "caller": (.84, 1.20, (154, 138, 93), 4, 1),
            "mimic": (.96, 1.03, (137, 141, 150), 3, 3),
            "armored": (1.39, 1.09, (104, 135, 126), 5, 1),
            "crawler": (1.66, .61, (137, 104, 143), 3, 1),
            "brute": (1.77, 1.32, (121, 104, 97), 2, 1),
        }
        sx, sy, tint, shirt, hair = proportions.get(variant, proportions["wanderer"])
        base = self.sprite(facing, frame, {"shirt": shirt, "hair_color": hair})
        width, height = base.get_size()
        sprite = pygame.Surface((width + 24, height + 3), pygame.SRCALPHA)
        center = sprite.get_width() // 2
        edge = -1 if facing == "left" else 1
        color = (65, 68, 61)
        if variant == "crawler":
            for side in (-1, 1):
                pygame.draw.lines(sprite, color, False, ((center + side*6, 30),
                                  (center + side*15, 41), (center + side*19, 59-frame%2*6)), 5)
                pygame.draw.line(sprite, tint, (center + side*15, 41), (center + side*19, 59-frame%2*6), 2)
        elif variant in ("brute", "armored"):
            for side in (-1, 1):
                extra = 6 if variant == "brute" and side == 1 else 0
                pygame.draw.polygon(sprite, color, ((center+side*4, 20-extra), (center+side*12, 17-extra),
                                    (center+side*17, 26), (center+side*12, 40), (center+side*5, 33)))
                pygame.draw.line(sprite, tint, (center+side*12, 20-extra), (center+side*15, 28), 3)
        sprite.blit(base, (12, 0))
        strength = .31 if variant == "mimic" else .61
        for y in range(sprite.get_height()):
            for x in range(sprite.get_width()):
                red, green, blue, alpha = sprite.get_at((x, y))
                if alpha:
                    shade = (red + green + blue) / 390
                    rgb = tuple(round(min(255, v * (1-strength) + tone * shade * strength))
                                for v, tone in zip((red, green, blue), tint))
                    sprite.set_at((x, y), (*rgb, alpha))
        if variant == "hunter":
            elbow = (center + 13*edge, 33)
            pygame.draw.lines(sprite, (82, 73, 57), False, ((center + 4*edge, 22), elbow,
                              (center + (14 + frame)*edge, 40)), 4)
        if variant == "caller":
            pygame.draw.arc(sprite, (176, 128, 76), (center-5, 13, 11, 12), math.pi, math.tau, 2)
        elif variant in ("brute", "crawler", "armored"):
            for i in range(3):
                pygame.draw.line(sprite, tint, (center+2+i, 27+i*4), (center+8-i, 23+i*5), 2)
        if facing != "up":
            injury = (93, 44, 56) if variant == "mimic" else (124, 52, 62)
            pygame.draw.lines(sprite, injury, False, ((center+1, 8), (center-1, 13), (center+3, 18)), 2)
        sprite = sprite.subsurface(sprite.get_bounding_rect()).copy()
        sprite = pygame.transform.smoothscale(sprite, (round(sprite.get_width()*sx), round(sprite.get_height()*sy)))
        stride_tilt = (-2, 4, 1, -5)[frame]
        lean = {"hunter": 9, "caller": -5, "crawler": 8, "mimic": 0, "brute": 3}.get(variant, 2)
        return pygame.transform.rotozoom(sprite, edge * (-14 if windup else stride_tilt - lean), 1)

    def draw_zombie(self, target, position, enemy, tick):
        variant = getattr(enemy, "kind", "wanderer")
        cadence = {"hunter": 126, "crawler": 111, "brute": 254, "mimic": 158}.get(variant, 212)
        frame = tick // cadence % 4 if enemy.moving else 0
        key = (variant, enemy.facing, frame, bool(enemy.windup))
        if key not in self.zombie_frames:
            self.zombie_frames[key] = self.zombie_sprite(*key)
        sprite = self.zombie_frames[key]
        x, y = map(round, position)
        target.blit(self.shadow, self.shadow.get_rect(center=(x, y)))
        if enemy.chasing or enemy.windup:
            ring = (219, 106, 79) if enemy.windup else (142, 103, 76)
            pygame.draw.ellipse(target, ring, (x - 22, y - 6, 44, 13), 2)
        target.blit(sprite, sprite.get_rect(midbottom=(x, y)))


class PaperWorld:
    def __init__(self):
        self.characters=Characters()
        self.collision_rects=[pygame.Rect(b["rect"].pixels()).inflate(4,4) for b in BUILDINGS]
        self.water_shapes=[(spec,smooth_polygon(spec['points'])) for spec in WATERS]
        self.island_shapes=[(spec,smooth_polygon(spec['points'])) for spec in ISLANDS]
        self.paths=[(spec,pixel_points(spec['points'])) for spec in ROADS+WALKWAYS]
        self.body_masks={}
        # One-bit water collision, with the actual shores, islands and bridges.
        water=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT),depth=8)
        water.fill((0,0,0)); water.set_colorkey((0,0,0))
        for _,points in self.water_shapes: pygame.draw.polygon(water,(255,255,255),points)
        for _,points in self.island_shapes: pygame.draw.polygon(water,(0,0,0),points)
        for spec,points in self.paths:
            if spec in WALKWAYS:
                stroke(
                    water,
                    (0,0,0),
                    smooth_path(points, closed=spec.get('closed',False)),
                    spec['width']*TILE,
                    closed=spec.get('closed',False),
                )
        for feature in LAKE_FEATURES:
            if feature['kind']=='pier':
                x,y=feature['tile']; pygame.draw.rect(water,(0,0,0),(x*TILE-22,y*TILE-16,65,32))
        self.water_mask=pygame.mask.from_surface(water)
        del water
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
        xin=load_image('xin-facade-v6.png')
        self.facades['xin_hall']=xin.subsurface(xin.get_bounding_rect(min_alpha=90)).copy()
        atlases={}
        for key,spec in ARCHITECTURE.items():
            if spec.get('renderer')=='tsinghua_lab':
                self.facades[key]=tsinghua_lab()
                continue
            if spec.get('renderer')=='life_science_2':
                self.facades[key]=life_science_2()
                continue
            if spec['art'] not in atlases: atlases[spec['art']]=load_image(spec['art'])
            sheet=atlases[spec['art']]; w,h=sheet.get_size()
            x,y,cw,ch=spec['crop']
            cell=sheet.subsurface(pygame.Rect(round(x*w),round(y*h),round(cw*w),round(ch*h))).copy()
            self.facades[key]=cell.subsurface(cell.get_bounding_rect(min_alpha=90)).copy()
        missing={b['id'] for b in BUILDINGS}-self.facades.keys()
        if missing: raise ValueError(f'Missing photo-referenced building facades: {sorted(missing)}')
        tree_sheet=load_image("trees-v5.png")
        self.tree_images=[crop_cell(tree_sheet,i%2,i//2) for i in range(4)]
        self.rooms=None
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
        self._landscapes(rng)

        # Draw all roads (fill only)
        for spec,points in self.paths:
            if spec in ROADS: self._paint_path(points,spec['width']*TILE,rng,mode='fill',closed=spec.get('closed',False))

        for _,points in self.water_shapes:
            self._paint_water(points,rng)
        for _,points in self.island_shapes:
            pygame.draw.polygon(self.ground,(164,166,129),points)
            pygame.draw.lines(self.ground,(124,145,120),True,points,5)

        # Draw all walkways (fill only)
        for spec,points in self.paths:
            if spec in WALKWAYS:
                self._paint_path(points,spec['width']*TILE,rng,spec.get('bridge',False),mode='fill',closed=spec.get('closed',False))

        for island in ISLANDS:
            if island.get('pavilion'): self._pavilion(pixel_points([island['center']])[0],21)
        for feature in LAKE_FEATURES: self._lake_feature(feature,rng)
        for field in SPORTS_FIELDS:
            rect=pygame.Rect(field.pixels())
            pygame.draw.rect(self.ground,(167,139,112),rect.inflate(10,10),border_radius=12)
            pygame.draw.rect(self.ground,(142,164,123),rect)
            pygame.draw.rect(self.ground,(237,232,211),rect.inflate(-20,-20),2)
            pygame.draw.line(self.ground,(237,232,211),(rect.centerx,rect.top+10),(rect.centerx,rect.bottom-10),2)
            pygame.draw.circle(self.ground,(237,232,211),rect.center,35,2)
        for building in BUILDINGS: self._building(building,rng)
        forbidden=list(self.collision_rects)
        forbidden += [pygame.Rect(b['rect'].pixels()).inflate(140,180) for b in BUILDINGS]
        forbidden += [pygame.Rect(v.pixels()).inflate(12,12) for v in SPORTS_FIELDS]
        forbidden += [pygame.Rect(round(self.door(b).x)-60,round(self.door(b).y)-15,120,120) for b in BUILDINGS]
        forbidden += [pygame.Rect(*tile_center(n['tile']),1,1).inflate(75,75) for n in NPCS]
        forbidden += [pygame.Rect(round(p['tile'][0]*TILE),round(p['tile'][1]*TILE),1,1).inflate(140,150) for p in LAKE_FEATURES]
        for shape in LANDSCAPES:
            points=pixel_points(shape['points'])
            forbidden.append(pygame.Rect(min(p.x for p in points),min(p.y for p in points),max(p.x for p in points)-min(p.x for p in points),max(p.y for p in points)-min(p.y for p in points)).inflate(30,30))
        for i in range(1500):
            x,y=rng.randrange(40,WORLD_WIDTH-40),rng.randrange(60,WORLD_HEIGHT-30)
            if any(r.colliderect(pygame.Rect(x-14,y-14,28,28)) for r in forbidden): continue
            if self.collides(pygame.Rect(x-14,y-14,28,28)): continue
            if any(distance_to_path((x,y),points)<spec['width']*TILE/2+45 for spec,points in self.paths): continue
            base=self.tree_images[i%4]
            h=rng.randrange(95,150); w=round(base.get_width()/base.get_height()*h)
            image=pygame.transform.smoothscale(base,(w,h))
            self.trees.append((x,y,image))
        self._entrance_details()
        self.minimap=pygame.transform.smoothscale(self.ground,(480,672))
        # Include symbolic foliage on the map without perspective or artwork UI.
        for x,y,_ in self.trees: pygame.draw.circle(self.minimap,(106,133,104),(round(x/WORLD_WIDTH*480),round(y/WORLD_HEIGHT*672)),1)

    def _landscapes(self,rng):
        for shape in LANDSCAPES:
            points=pixel_points(shape['points'])
            color=(143,165,117) if shape['kind']=='lawn' else (205,205,189)
            pygame.draw.polygon(self.ground,color,points)
            mask=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT),depth=8)
            # Clip small original brush marks to the authored open lawn/plaza.
            mask.fill((0,0,0));pygame.draw.polygon(mask,(255,255,255),points)
            bounds=pygame.Rect(min(p.x for p in points),min(p.y for p in points),max(p.x for p in points)-min(p.x for p in points),max(p.y for p in points)-min(p.y for p in points))
            if shape['kind']=='lawn':
                for _ in range(bounds.width*bounds.height//160):
                    x,y=rng.randrange(bounds.left,bounds.right),rng.randrange(bounds.top,bounds.bottom)
                    if mask.get_at((x,y)).r:
                        pygame.draw.aaline(self.ground,rng.choice(((133,156,108),(151,171,126),(139,162,114))),(x,y),(x+rng.randrange(3,9),y-1))
            else:
                for y in range(bounds.top,bounds.bottom,26):
                    for x in range(bounds.left,bounds.right,48):
                        if mask.get_at((x,y)).r: pygame.draw.line(self.ground,(186,190,175),(x,y),(x+25,y),1)
            del mask

    def _entrance_details(self):
        # The north gate is an open green plaza with the book-shaped monument,
        # not a fantasy arch across the access road. Draw original flat 2D details.
        x,y=149*TILE,39*TILE
        pygame.draw.ellipse(self.ground,(166,176,150),(x-45,y-12,90,34))
        for index in range(3):
            px=x-19+index*14
            pygame.draw.rect(self.ground,(225+index*5,225+index*5,207+index*5),(px,y-152,12,153))
            pygame.draw.line(self.ground,(175,184,167),(px,y-151),(px,y),1)
            for py in (y-122,y-54): pygame.draw.line(self.ground,(185,191,175),(px,py),(px+12,py),3)
        font=pygame.font.SysFont('microsoftjhenghei',11)
        for index,char in enumerate('國立清華大學'):
            self.ground.blit(font.render(char,True,(75,87,69)),(x-3,y-117+index*13))
        # Open plaza seating, planted edges and the Campus Green flag platform.
        for tx,ty in ((140,36),(146,44),(120,51),(118,59)):
            bx,by=tx*TILE,ty*TILE
            pygame.draw.rect(self.ground,(112,119,97),(bx-27,by-3,54,13),border_radius=2)
            for dy in (0,4,8): pygame.draw.line(self.ground,(174,158,126),(bx-25,by+dy),(bx+25,by+dy),2)
        fx,fy=121*TILE,53*TILE
        pygame.draw.ellipse(self.ground,(193,191,167),(fx-26,fy-9,52,22))
        pygame.draw.line(self.ground,(117,125,113),(fx,fy),(fx,fy-97),3)
        pygame.draw.polygon(self.ground,(126,97,109),[(fx+2,fy-97),(fx+35,fy-93),(fx+28,fy-76),(fx+2,fy-80)])
        cx,cy=107*TILE,71*TILE
        pygame.draw.polygon(self.ground,(145,153,131),[(cx-18,cy+7),(cx+18,cy+7),(cx+7,cy-39),(cx-7,cy-39)])
        pygame.draw.circle(self.ground,(224,221,197),(cx,cy-39),15)
        pygame.draw.circle(self.ground,(104,119,103),(cx,cy-39),15,2)
        pygame.draw.line(self.ground,(72,91,76),(cx,cy-39),(cx,cy-48),2)
        pygame.draw.line(self.ground,(72,91,76),(cx,cy-39),(cx+7,cy-36),2)

    def _paint_path(self,points,width,rng,wood=False,mode='both',closed=False):
        color=(169,143,110) if wood else (207,200,178)
        points=smooth_path(points,closed=closed)
        # Borderless rendering: Ignore edge mode, only draw fill.
        if mode in ('fill', 'both'):
            stroke(self.ground,color,points,width,end_caps=not closed,closed=closed)
            for a,b in zip(points,points[1:]):
                segment=b-a
                if not segment.length_squared(): continue
                tangent=segment.normalize(); normal=pygame.Vector2(-tangent.y,tangent.x)
                for step in range(0,round(segment.length()),10 if wood else 22):
                    center=a+tangent*step
                    extent=width*.45 if wood else rng.uniform(.15,.42)*width
                    shade=(130,112,89) if wood else (191+rng.randrange(10),188,168)
                    pygame.draw.aaline(self.ground,shade,center-normal*extent,center+normal*extent)
                if wood:
                    for side in (-1,1):
                        rail_a,rail_b=a+normal*(width/2+2)*side,b+normal*(width/2+2)*side
                        pygame.draw.line(self.ground,(102,111,94),rail_a,rail_b,3)
                        for step in range(0,round(segment.length()),36):
                            point=rail_a+tangent*step
                            pygame.draw.line(self.ground,(93,104,88),point,point+(0,-9),3)

    def _paint_water(self,points,rng):
        rect=pygame.Rect(min(x for x,y in points),min(y for x,y in points),1,1)
        rect.width=max(x for x,y in points)-rect.x+1
        rect.height=max(y for x,y in points)-rect.y+1
        local=[(x-rect.x,y-rect.y) for x,y in points]
        texture=pygame.Surface(rect.size,pygame.SRCALPHA)
        # Broad matte washes avoid the visible square seams of repeating water tiles.
        texture.fill((103,148,150))
        wash=pygame.Surface(rect.size,pygame.SRCALPHA)
        for _ in range(90):
            x,y=rng.randrange(-100,rect.width),rng.randrange(-40,rect.height)
            color=rng.choice(((163,178,156,10),(57,119,134,12),(127,164,156,12)))
            pygame.draw.ellipse(wash,color,(x,y,rng.randrange(90,340),rng.randrange(25,130)))
        texture.blit(wash,(0,0))
        for _ in range(rect.width*rect.height//650):
            x,y=rng.randrange(rect.width),rng.randrange(rect.height)
            pygame.draw.aaline(texture,(149,178,169),(x,y),(x+rng.randrange(5,20),y))
        mask=pygame.Surface(rect.size,pygame.SRCALPHA)
        pygame.draw.polygon(mask,(255,255,255),local)
        texture.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
        pygame.draw.lines(self.ground,(138,157,129),True,points,18)
        self.ground.blit(texture,rect)
        pygame.draw.aalines(self.ground,(168,185,157),True,points)
        # Sparse reeds and flowers follow the authored shoreline, never a box.
        for index in range(0,len(points),5):
            x,y=points[index]
            for _ in range(4):
                px,py=x+rng.randrange(-13,14),y+rng.randrange(-10,11)
                pygame.draw.line(self.ground,(121,145,110),(px,py),(px+rng.randrange(-3,4),py-rng.randrange(4,12)),1)
            if index%15==0:
                pygame.draw.circle(self.ground,rng.choice(((191,173,146),(162,151,158),(199,193,154))),(x+5,y-6),2)

    def _pavilion(self,center,radius=26):
        x,y=map(round,center)
        pygame.draw.ellipse(self.ground,(127,133,107),(x-radius,y-8,radius*2,20))
        for dx in (-radius*.65,radius*.65): pygame.draw.line(self.ground,(103,98,77),(x+dx,y),(x+dx,y-27),4)
        roof=[(x+math.cos(i*math.tau/8)*radius,y-27+math.sin(i*math.tau/8)*radius*.45) for i in range(8)]
        pygame.draw.polygon(self.ground,(112,114,91),roof)
        pygame.draw.aalines(self.ground,(77,91,76),True,roof)
        for point in roof: pygame.draw.aaline(self.ground,(147,143,111),(x,y-32),point)

    def _lake_feature(self,feature,rng):
        x,y=pixel_points([feature['tile']])[0]
        kind=feature['kind']
        if kind=='pavilion': self._pavilion((x,y),30)
        elif kind=='pier':
            pygame.draw.rect(self.ground,(157,132,99),(x-22,y-16,65,32))
            for px in range(round(x-22),round(x+43),8): pygame.draw.line(self.ground,(118,113,91),(px,y-16),(px,y+16),1)
        elif kind=='steps':
            for i in range(6):
                pygame.draw.arc(self.ground,(189-i*5,182-i*4,154-i*3),(x-65+i*6,y-38+i*5,130-i*12,76-i*8),0,math.pi,4)
        else:
            for _ in range(30):
                px,py=x+rng.randrange(-38,39),y+rng.randrange(-26,27)
                pygame.draw.circle(self.ground,rng.choice(((178,167,133),(159,141,144),(126,150,108))),(round(px),round(py)),3)

    def _building(self,b,rng):
        rect=pygame.Rect(b["rect"].pixels())
        pygame.draw.rect(self.ground,(204,200,179),(rect.left-3,rect.bottom-3,rect.width+6,12),border_radius=3)
        original=self.facades[b["id"]]
        self.ground.blit(pygame.transform.smoothscale(original,rect.size),rect)
        door=self.door(b)
        pygame.draw.rect(self.ground,(220,215,194),(door.x-27,rect.bottom-3,54,13))
        pygame.draw.line(self.ground,(174,171,153),(door.x-27,rect.bottom+4),(door.x+27,rect.bottom+4),1)
        # Explicit approaches follow the plan; never draw a shortcut through a lake.
        points=[door]+pixel_points(b.get('access',[]))
        if len(points)>1:
            self._paint_path(points,23,rng)
            self.paths.append(({'width':23/TILE},points))

    def door(self,b):
        rect=pygame.Rect(b["rect"].pixels())
        return pygame.Vector2(rect.centerx,rect.bottom+17)

    def collides(self,rect):
        if rect.left<10 or rect.top<10 or rect.right>WORLD_WIDTH-10 or rect.bottom>WORLD_HEIGHT-10: return True
        if any(rect.colliderect(r) for r in self.collision_rects): return True
        size=rect.size
        if size not in self.body_masks: self.body_masks[size]=pygame.Mask(size,fill=True)
        return self.water_mask.overlap(self.body_masks[size],rect.topleft) is not None

    def camera_for(self,x,y):
        return pygame.Rect(max(0,min(WORLD_WIDTH-INTERNAL_WIDTH,round(x-INTERNAL_WIDTH/2))),max(0,min(WORLD_HEIGHT-INTERNAL_HEIGHT,round(y-INTERNAL_HEIGHT/2))),INTERNAL_WIDTH,INTERNAL_HEIGHT)

    def draw_view(self,target,camera,actors,state,moving,tick,riding_bike=False,enemies=(),survivors=()):
        target.blit(self.ground,(0,0),camera)
        layers=[]
        for x,y,image in self.trees:
            if camera.inflate(200,200).collidepoint(x,y): layers.append((y,"tree",(x,y,image)))
        for actor in actors:
            x,y=tile_center(actor["tile"])
            if camera.inflate(100,100).collidepoint(x,y): layers.append((y,"npc",actor))
        for actor in survivors:
            if camera.inflate(100,100).collidepoint(actor.position):
                layers.append((actor.position[1],"survivor",actor))
        for enemy in enemies:
            if camera.inflate(160,160).collidepoint(enemy.position):
                layers.append((enemy.position[1],"zombie",enemy))
        layers.append((state.player_y,"player",None))
        for _,kind,value in sorted(layers,key=lambda v:v[0]):
            if kind=="tree":
                x,y,image=value
                target.blit(image,(x-camera.x-image.get_width()/2,y-camera.y-image.get_height()+12))
            elif kind=="zombie":
                self.characters.draw_zombie(target,pygame.Vector2(value.position)-pygame.Vector2(camera.topleft),value,tick)
            else:
                if kind=="player": x,y=state.player_x,state.player_y; appearance=state.appearance; facing=state.facing
                elif kind=="survivor":
                    x,y=value.position; identity=getattr(value,"identity",-1)
                    n=identity+17 if identity>=0 else sum(map(ord,value.kind))
                    appearance={"shirt":n%6,"hair_color":n%5,"skin":n%4,"hair_style":n%4,"gender":n%2}; facing=value.facing
                else:
                    x,y=tile_center(value["tile"]); n=sum(map(ord,value["id"]))
                    appearance={"shirt":n%6,"hair_color":n%5,"skin":n%4,"hair_style":n%4}; facing="down"
                if kind=="player" and riding_bike:
                    bike_facing=facing if facing in ("left","right") else "right"
                    self.characters.draw_bike(target,(x-camera.x,y-camera.y),bike_facing,moving,tick,appearance)
                else:
                    self.characters.draw(target,(x-camera.x,y-camera.y),facing,moving if kind=="player" else value.moving if kind=="survivor" else False,appearance,tick,
                                         running=kind=="player" and getattr(state, "running", False),
                                         stride=getattr(value, "stride", None) if kind=="survivor" else None)
        # Sparse restrained ripple motion, not floating pickup sparkles.
        for spec,points in self.water_shapes:
            water=pygame.Rect(min(x for x,y in points),min(y for x,y in points),1,1)
            water.width=max(x for x,y in points)-water.x
            water.height=max(y for x,y in points)-water.y
            if not water.colliderect(camera): continue
            for i in range(10):
                x=water.left+(i*83+tick//120)%max(1,water.width)
                y=water.top+(i*67)%max(1,water.height)
                if self.water_mask.get_at((x,y)) and self.water_mask.get_at((min(WORLD_WIDTH-1,x+12),y)):
                    pygame.draw.aaline(target,(153,183,177),(x-camera.x,y-camera.y),(x-camera.x+12,y-camera.y))

    def room_image(self,building,size):
        if self.rooms is None:
            room_sheet=load_image("room-plans-v5.png")
            w,h=room_sheet.get_width()//2,room_sheet.get_height()//2
            self.rooms=[room_sheet.subsurface((i%2*w,i//2*h,w,h)).copy() for i in range(4)]
        style=building.get("style","")
        index=0 if building["id"] in DORMS else 1 if "library" in building["id"] else 2 if style in ("dining","activity") else 3
        return pygame.transform.smoothscale(self.rooms[index],size)
