"""Original flat elevation for Tsing Hua Laboratory, drawn from photo references."""
import random
import pygame


def life_science_2():
    """Detailed Life Science II elevation: stepped laboratory wings and blue-green glass."""
    canvas = pygame.Surface((920, 540), pygame.SRCALPHA)
    ink = (61, 69, 68)

    def rect(rect, color, border=0):
        pygame.draw.rect(canvas, color, rect)
        if border:
            pygame.draw.rect(canvas, ink, rect, border)

    # Warm concrete masses under a hard afternoon shadow.
    rect((24, 126, 294, 382), (190, 188, 174), 1)
    rect((318, 82, 286, 426), (205, 203, 188), 1)
    rect((604, 142, 292, 366), (181, 184, 174), 1)
    rect((24, 126, 294, 20), (222, 219, 202))
    rect((318, 82, 286, 18), (224, 222, 207))
    rect((604, 142, 292, 18), (216, 215, 202))

    # Recessed blue-green laboratory windows with metallic mullions.
    for left, top, cols, rows, dx, dy in (
        (48, 170, 6, 5, 40, 58),
        (344, 124, 5, 6, 48, 52),
        (628, 184, 6, 5, 40, 55),
    ):
        for row in range(rows):
            for col in range(cols):
                x = left + col * dx
                y = top + row * dy
                color = (58 + (row + col) % 3 * 5, 91 + (row + col) % 2 * 8, 104 + col % 2 * 7)
                rect((x, y, dx - 10, dy - 18), color)
                pygame.draw.line(canvas, (128, 155, 151), (x + 3, y + 3), (x + dx - 13, y + 3), 2)
                pygame.draw.line(canvas, (32, 62, 68), (x + dx - 13, y), (x + dx - 13, y + dy - 18), 2)
                if (row + col) % 4 == 0:
                    pygame.draw.line(canvas, (177, 190, 177), (x + 5, y + 5), (x + 18, y + 20), 2)

    # Central glazed stair atrium and the projecting entrance frame.
    rect((354, 54, 214, 454), (74, 112, 119), 1)
    rect((366, 66, 190, 442), (93, 137, 143), 1)
    for x in range(372, 557, 25):
        rect((x, 68, 15, 438), (86 + (x // 25) % 3 * 7, 132, 140))
        pygame.draw.line(canvas, (178, 193, 186), (x - 2, 68), (x - 2, 506), 2)
    for y in range(118, 492, 56):
        pygame.draw.line(canvas, (158, 178, 170), (356, y), (568, y), 3)
    rect((330, 38, 262, 18), (180, 181, 169))
    pygame.draw.polygon(canvas, (119, 126, 119), [(330, 38), (592, 38), (568, 22), (354, 22)])
    rect((342, 432, 236, 108), (67, 88, 89), 1)
    rect((374, 444, 172, 96), (84, 124, 126), 1)
    for x in range(382, 540, 30):
        pygame.draw.line(canvas, (174, 188, 180), (x, 446), (x + 9, 539), 4)
    rect((360, 416, 200, 16), (213, 210, 193), 1)

    # Ground-level stone piers, planters and broad canopy.
    rect((24, 474, 294, 34), (211, 207, 192))
    rect((604, 474, 292, 34), (202, 200, 187))
    rect((280, 430, 38, 78), (159, 160, 151), 1)
    rect((602, 430, 38, 78), (153, 157, 148), 1)
    rect((292, 420, 336, 15), (225, 220, 199), 1)
    rect((300, 434, 320, 8), (165, 169, 158))

    # Matte grain and narrow cast shadow at the feet.
    rng = random.Random(2026)
    for _ in range(22000):
        x = rng.randrange(920)
        y = rng.randrange(540)
        color = canvas.get_at((x, y))
        if color.a:
            delta = rng.choice((-4, -3, 2, 3))
            canvas.set_at((x, y), (*(max(0, min(255, c + delta)) for c in color[:3]), color.a))
    rect((12, 506, 896, 16), (54, 68, 63))
    rect((12, 506, 896, 4), (92, 105, 95))
    return canvas.subsurface(canvas.get_bounding_rect(min_alpha=90)).copy()


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
