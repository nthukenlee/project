"""Original flat elevation for Tsing Hua Laboratory, drawn from photo references."""
import random
import pygame


def tsinghua_lab():
    canvas=pygame.Surface((920,540),pygame.SRCALPHA)
    ink=(80,87,84)
    def wall(rect,color):
        pygame.draw.rect(canvas,color,rect)
        pygame.draw.rect(canvas,ink,rect,1)
    def windows(x,y,cols,rows,w,h,dx,dy):
        for row in range(rows):
            for col in range(cols):
                rect=pygame.Rect(x+col*dx,y+row*dy,w,h)
                wall(rect,(76,109,122))
                pygame.draw.line(canvas,(168,184,178),rect.midtop,rect.midbottom,2)
                pygame.draw.line(canvas,(168,184,178),rect.midleft,rect.midright,1)
    # Side wings and their horizontal bands, not a generic repeated glass box.
    wall((30,118,345,400),(209,202,185))
    windows(47,420,8,2,25,28,40,42)
    wall((646,94,235,420),(167,144,140))
    for y in range(143,463,53):
        wall((646,y,235,8),(201,195,184))
    windows(682,113,3,7,43,29,61,53)
    wall((565,143,81,301),(192,179,157))
    for y in range(165,425,51):
        wall((571,y,75,23),(103,111,103))
        pygame.draw.line(canvas,(220,214,195),(569,y+24),(645,y+24),4)
    # Long brown louvres on the entire left wing.
    for y in range(135,414,48):
        wall((48,y,310,35),(104,112,108))
        for offset in (0,8,16,24):
            pygame.draw.line(canvas,(159,133,105),(48,y+offset),(358,y+offset),4)
    # Central glass shaft, visible silver mullions and slender roof projection.
    wall((367,46,204,409),(81,118,141))
    for col in range(8):
        x=373+col*25
        wall((x,52,18,391),(78+col%3*6,117+col%2*9,142+col%3*6))
        pygame.draw.line(canvas,(203,207,192),(x-2,52),(x-2,443),3)
    for y in range(98,438,56):
        pygame.draw.line(canvas,(172,188,185),(369,y),(568,y),3)
    wall((354,34,232,13),(192,194,180))
    # Raised connecting canopy and angled glass supports from the official view.
    wall((346,368,561,21),(205,202,179))
    for x in range(350,904,7):
        pygame.draw.line(canvas,(152,160,148),(x,361),(x,367),1)
    wall((383,390,204,102),(89,122,130))
    for x in range(389,586,32):
        pygame.draw.line(canvas,(207,208,190),(x,392),(x+12,488),5)
    wall((405,492,128,31),(64,83,83))
    windows(416,497,3,1,29,24,36,28)
    for x in (374,574): wall((x,490,12,35),(181,176,156))
    wall((389,524,161,8),(181,176,156))
    # Subtle matte grain stays inside opaque architecture, with a fixed seed.
    rng=random.Random(636)
    for _ in range(28000):
        x,y=rng.randrange(920),rng.randrange(540)
        color=canvas.get_at((x,y))
        if color.a:
            delta=rng.choice((-5,-3,2,4))
            canvas.set_at((x,y),(*(max(0,min(255,c+delta)) for c in color[:3]),color.a))
    return canvas.subsurface(canvas.get_bounding_rect(min_alpha=90)).copy()
