from __future__ import annotations
from dataclasses import dataclass
import re
import pygame

INK=(42,57,51)
PAPER=(247,244,234)
MUTED=(105,116,104)
GREEN=(68,98,85)
LINE=(205,210,192)

class FontBook:
    def __init__(self):
        self.name=pygame.font.match_font('microsoftjhenghei') or pygame.font.match_font('notosanscjktc') or pygame.font.match_font('arial')
        self.cache={}
    def get(self,size,bold=False):
        key=(size,bold)
        if key not in self.cache: self.cache[key]=pygame.font.Font(self.name,size); self.cache[key].set_bold(bold)
        return self.cache[key]
    def draw(self,target,text,pos,size=20,color=INK,bold=False,anchor='topleft'):
        image=self.get(size,bold).render(str(text),True,color)
        rect=image.get_rect(); setattr(rect,anchor,pos); target.blit(image,rect); return rect
    def wrapped(self,text,size,width):
        lines=[]
        for paragraph in str(text).splitlines() or ['']:
            line=''
            # Keep English words together; CJK remains individually wrappable.
            for token in re.findall(r"[A-Za-z0-9]+(?:['’/-][A-Za-z0-9]+)*|[^\S\r\n]+|.",paragraph):
                if line and self.get(size).size(line+token)[0]>width:
                    lines.append(line.rstrip()); line=''; token=token.lstrip()
                if not line and not token.strip(): continue
                for char in token:
                    if line and self.get(size).size(line+char)[0]>width:
                        lines.append(line); line=char
                    else: line+=char
            lines.append(line.rstrip())
        return lines

def panel(target,rect,fill=PAPER,alpha=245):
    rect=pygame.Rect(rect)
    layer=pygame.Surface(rect.size,pygame.SRCALPHA)
    pygame.draw.rect(layer,(*fill,alpha),layer.get_rect(),border_radius=12)
    target.blit(layer,rect)
    pygame.draw.rect(target,LINE,rect,1,border_radius=12)

@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    enabled: bool=True
    primary: bool=False
    def draw(self,target,fonts,mouse):
        hovered=self.enabled and self.rect.collidepoint(mouse)
        fill=GREEN if self.primary else (232,235,220) if hovered else PAPER
        color=PAPER if self.primary else INK if self.enabled else (160,166,153)
        if self.primary and hovered: fill=(80,113,97)
        pygame.draw.rect(target,fill,self.rect,border_radius=9)
        pygame.draw.rect(target,LINE,self.rect,1,border_radius=9)
        size=19
        while size>12 and fonts.get(size,self.primary).size(self.label)[0]>self.rect.width-18: size-=1
        fonts.draw(target,self.label,self.rect.center,size,color,self.primary,'center')
