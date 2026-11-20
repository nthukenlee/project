"""Playable interpretations of public campus rooms, using original procedural art."""
import pygame

from .interiors import Fixture, Room

WOOD = (149, 108, 72)
DARK_WOOD = (102, 76, 58)
GLASS = (83, 121, 119)
TEAL = (69, 105, 100)
STEEL = (127, 139, 135)
RUST = (143, 73, 61)
LINEN = (193, 182, 153)


def hall(key, outline, entry, event, palette, labels, *, wood=False, side=None):
    fixtures = [("room_detail", event)]
    if side:
        fixtures.append(("side_exit", side))
    room = Room(key, outline, entry, fixtures, labels)
    room.event_point = event
    room.paint_floor(palette, 8, wood=wood)
    pygame.draw.lines(room.surface, (76, 80, 73), True, outline, 7)
    for a, b in zip(outline, outline[1:] + outline[:1]):
        a, b = pygame.Vector2(a), pygame.Vector2(b)
        if a.distance_to(b) > 40:
            pygame.draw.line(room.surface, (153, 147, 122), a.lerp(b,.025)+(0,6), a.lerp(b,.975)+(0,6), 3)
    return room


def window(room, x, y, width):
    pygame.draw.rect(room.surface, (56, 78, 78), (x, y, width, 20), border_radius=2)
    pygame.draw.rect(room.surface, GLASS, (x+3, y+3, width-6, 14))
    for cross in range(x+30, x+width-4, 31):
        pygame.draw.line(room.surface, (167, 182, 163), (cross, y+3),(cross,y+17),2)
        pygame.draw.aaline(room.surface, (195, 196, 161), (cross-18,y+5),(cross-9,y+14))


def table_row(room, xs, ys, color, *, size=(56, 24)):
    for x in xs:
        for y in ys:
            w,h = size
            room.fixture((x,y,w,h), color, "desk")
            pygame.draw.rect(room.surface, (82, 100, 95), (x+w//3,y+h+4,w//3,9), border_radius=3)


def steps(room, x, y, width=100):
    room.wall((x, y, width, 47), (135, 134, 117))
    for offset in range(6, 45, 7):
        pygame.draw.line(room.surface, (194, 177, 140), (x+5,y+offset),(x+width-6,y+offset),1)


def general_two():
    room = hall("general_2", [(170,106),(1082,106),(1082,582),(782,582),(782,540),(170,540)],
                (220,476),(809,319),(162,161,143), [("room.class103",(412,152)),("room.concourse",(480,482))], side=(1040,521))
    window(room,205,116,555)
    room.wall((767,131,16,233))
    room.wall((199,392,465,16))
    room.wall((746,392,256,16))
    pygame.draw.rect(room.surface,TEAL,(318,173,209,12))
    table_row(room,(272,385,498,611),(221,284,348),WOOD)
    room.fixture((864,176,121,36),DARK_WOOD,"books")
    room.plant(1021,475)
    steps(room,827,265)
    return room.finish()


def general_three():
    room = hall("general_3", [(162,159),(403,159),(403,105),(1089,105),(1089,553),(647,553),(647,599),(162,599)],
                (219,538),(925,314),(157,166,157), [("room.groupclass",(831,135)),("room.noticehall",(317,405))])
    window(room,421,115,618)
    room.wall((478,136,14,233))
    room.wall((478,445,14,151))
    room.wall((630,404,390,14))
    for x, y in ((587,229),(741,243),(930,242),(672,341),(861,349)):
        room.fixture((x,y,91,32),(146,128,95),"round")
        pygame.draw.circle(room.surface,RUST,(x+15,y+38),9)
        pygame.draw.circle(room.surface,TEAL,(x+68,y+39),9)
    room.fixture((222,182,67,100),STEEL,"books")
    steps(room,290,462,145)
    room.plant(1047,493)
    return room.finish()


def general_four():
    room = hall("general_4", [(200,138),(1085,138),(1085,543),(705,543),(705,595),(200,595)],
                (243,528),(435,322),(176,158,135), [("room.postdesk",(376,211)),("room.class121",(835,189))])
    window(room,225,151,285)
    window(room,611,151,430)
    room.wall((548,158,16,242))
    room.wall((548,470,16,115))
    room.fixture((241,268,235,31),(137,105,68),"desk")
    room.fixture((268,204,130,24),STEEL,"books")
    for x in (260, 343, 426):
        room.fixture((x,417,39,21),(136,125,94))
    pygame.draw.rect(room.surface,(49,80,66),(674,198,258,14))
    table_row(room,(622,731,840,950),(242,309,370),(157,131,96),size=(70,24))
    room.plant(1029,462)
    return room.finish()


def engineering():
    room = hall("engineering_1", [(153,140),(399,140),(399,102),(1052,102),(1052,223),(1110,223),(1110,560),(274,560),(274,600),(153,600)],
                (204,544),(754,315),(161,156,135), [("room.eng101",(636,149)),("room.workcorridor",(369,484))], side=(1078,507))
    window(room,415,115,572)
    room.wall((281,382,432,16))
    room.wall((784,382,306,16))
    room.wall((411,139,16,213))
    pygame.draw.rect(room.surface,(55,77,66),(499,172,400,14))
    table_row(room,(485,608,731,855),(217,274,337),WOOD,size=(84,25))
    room.fixture((181,194,122,36),STEEL,"books")
    steps(room,312,425)
    room.fixture((896,454,113,32),(126,115,87),"desk")
    room.plant(1048,280)
    return room.finish()


def physics():
    room = hall("physics", [(250,108),(1038,108),(1102,209),(1102,562),(179,562),(179,213)],
                (237,519),(875,374),(151,165,165), [("room.demonstration",(676,150)),("room.foyer",(451,510))])
    window(room,265,118,701)
    room.wall((229,416,302,15),(115,133,134))
    room.wall((605,416,442,15),(115,133,134))
    room.fixture((485,184,319,38),TEAL,"desk")
    for y in (252,306,355):
        for x in (339,521,703,885):
            room.fixture((x,y,125,15),(125,124,114))
    room.fixture((230,459,124,28),STEEL,"books")
    room.plant(1011,495)
    return room.finish()


def chemistry():
    room = hall("chemistry", [(193,118),(1097,118),(1097,579),(843,579),(843,616),(438,616),(438,536),(193,536)],
                (246,491),(790,374),(170,168,152), [("room.teaching",(447,145)),("room.seminar",(912,161))], side=(1038,534))
    window(room,218,130,505)
    window(room,811,130,249)
    room.wall((733,151,16,261))
    room.wall((216,418,338,16))
    room.wall((644,418,405,16))
    table_row(room,(274,412,550),(205,277,352),STEEL,size=(93,32))
    room.fixture((844,221,171,68),(122,145,137),"round")
    room.fixture((484,523,106,24),DARK_WOOD,"books")
    steps(room,873,466,112)
    room.plant(1036,324)
    return room.finish()


def sports():
    room = hall("gym", [(124,124),(1150,124),(1150,566),(124,566)], (186,513),(934,374),
                (171,138,97), [("room.court_floor",(621,156)),("room.spectator",(291,525))], wood=True, side=(1102,511))
    box=pygame.Rect(235,190,809,286)
    pygame.draw.rect(room.surface,(194,152,103),box,border_radius=4)
    pygame.draw.rect(room.surface,(233,220,187),box,3)
    pygame.draw.line(room.surface,(233,220,187),box.midtop,box.midbottom,3)
    pygame.draw.circle(room.surface,(232,220,187),box.center,59,3)
    for x in (box.left,box.right-125):
        pygame.draw.rect(room.surface,(237,220,181),(x,267,125,132),3)
        pygame.draw.circle(room.surface,RUST,(x+50,333),17,3)
    for x in (257,452,648,841):
        room.fixture((x,488,144,19),(130,113,84))
    room.fixture((1004,143,101,23),STEEL,"desk")
    return room.finish()


def food_court():
    room = hall("dining_hall", [(142,122),(1115,122),(1115,555),(910,555),(910,606),(142,606)],
                (199,542),(824,335),(165,158,139), [("room.stalls",(628,152)),("room.tables",(530,524))])
    for i,x in enumerate((185,411,637,863)):
        tint=(TEAL,RUST,(163,132,82),STEEL)[i]
        room.fixture((x,188,172,47),tint,"desk")
        pygame.draw.rect(room.surface,tint,(x,161,172,12),border_radius=3)
        pygame.draw.rect(room.surface,(179,166,140),(x+5,175,162,8))
        for n in range(4):
            pygame.draw.circle(room.surface,LINEN,(x+21+n*36,211),7)
    for x,y in ((262,334),(459,333),(637,347),(331,430),(574,445),(778,443),(957,427)):
        room.fixture((x,y,91,23),WOOD,"round")
        for dx in (12,69):
            pygame.draw.rect(room.surface,TEAL,(x+dx,y+28,14,10),border_radius=3)
    room.plant(1060,512)
    return room.finish()


def ren():
    room = hall("ren_hall", [(232,119),(1077,119),(1077,563),(322,563),(322,609),(232,609)],
                (275,551),(801,363),(150,156,136), [("room.ren_common",(675,519)),("room.reading",(947,153))])
    window(room,546,133,461)
    room.wall((328,172,13,282))
    room.fixture((365,210,57,151),RUST,"sofa")
    table_row(room,(489,712),(240,421),DARK_WOOD,size=(155,51))
    room.fixture((932,179,90,30),DARK_WOOD,"books")
    room.fixture((892,378,140,33),WOOD,"books")
    room.plant(1041,489)
    steps(room,359,477)
    return room.finish()


def shi():
    room = hall("shi_hall", [(159,182),(401,182),(401,111),(1101,111),(1101,571),(160,571)], (211,520),
                (819,365),(169,169,157), [("room.shi_common",(749,536)),("room.kitchen",(756,157))])
    window(room,427,121,624)
    room.fixture((432,175,472,32),(127,128,115),"desk")
    room.fixture((165,200,90,139),DARK_WOOD,"books")
    room.wall((335,216,16,254))
    for x,y,w,h in ((409,406,89,53),(536,250,132,55),(637,385,131,48),(913,252,88,47),(927,419,101,56)):
        room.fixture((x,y,w,h),WOOD if w>100 else LINEN,"round")
        pygame.draw.circle(room.surface,(68,78,76),(x+16,y+h+13),10)
        pygame.draw.circle(room.surface,(84,88,83),(x+w-17,y+h+13),10)
    room.plant(1048,524)
    return room.finish()


def li():
    room = hall("li_hall", [(162,122),(1014,122),(1108,214),(1108,583),(350,583),(350,611),(162,611)],
                (213,547),(800,391),(154,128,103), [("room.li_common",(843,541)),("room.parcel",(288,204))], wood=True)
    window(room,497,134,463)
    window(room,1021,230,71)
    room.wall((419,172,16,239))
    room.fixture((211,230,157,48),(151,122,89),"desk")
    room.fixture((207,181,130,20),DARK_WOOD,"books")
    room.fixture((623,183,262,40),(50,64,66),"sofa")
    room.fixture((919,230,48,116),(58,65,67),"sofa")
    room.fixture((766,264,107,37),WOOD,"round")
    for x,y in ((475,379),(604,420),(952,458)):
        room.fixture((x,y,163,46),DARK_WOOD,"books")
    room.plant(1049,521)
    steps(room,224,423,121)
    return room.finish()


def yi():
    room = hall("yi_hall", [(319,108),(958,108),(1092,206),(1092,573),(766,573),(766,605),(230,605),(230,239)],
                (270,546),(868,369),(164,165,150), [("room.yi_common",(730,525)),("room.service",(393,195))])
    window(room,365,121,544)
    for x,y in ((376,236),(983,227),(947,497)):
        room.fixture((x,y,111,28),DARK_WOOD,"books")
    pygame.draw.polygon(room.surface,(140,155,141),[(494,220),(912,224),(960,437),(773,500),(483,442)])
    for x,y in ((582,280),(704,265),(801,280),(922,304),(531,400)):
        room.fixture((x,y,112,38),(126,127,120),"round")
        pygame.draw.circle(room.surface,WOOD,(x+10,y+48),8)
    room.wall((346,344,15,188))
    room.plant(1004,431)
    steps(room,393,485)
    return room.finish()


def administration():
    room = hall("admin_hall", [(136,111),(775,111),(775,151),(1118,151),(1118,578),(456,578),(456,617),(136,617)],
                (194,559),(566,353),(178,168,145),
                [("room.admin_service",(489,166)),("room.admin_auditorium",(945,209))])
    window(room,168,124,571)
    room.wall((759,160,16,238))
    room.wall((759,476,16,98))
    room.fixture((242,219,364,42),WOOD,"desk")
    room.fixture((243,181,172,21),DARK_WOOD,"books")
    room.fixture((883,246,132,33),RUST,"sofa")
    for y in (326,391):
        room.fixture((891,y,126,24),DARK_WOOD)
    steps(room,212,375,125)
    room.plant(707,310)
    return room.finish()


def engineering_three():
    room = hall("engineering_2", [(164,183),(406,183),(406,115),(1073,115),(1073,593),(165,593)],
                (213,531),(687,392),(157,165,158),
                [("room.eng2_work",(738,154)),("room.eng2_crossing",(454,544))], side=(1024,535))
    window(room,433,130,606)
    room.wall((312,211,14,243),STEEL)
    room.wall((416,454,205,15),STEEL)
    room.wall((699,454,344,15),STEEL)
    room.fixture((461,197,281,31),TEAL,"desk")
    table_row(room,(452,579,748,899),(273,350),STEEL,size=(95,30))
    room.fixture((211,239,57,109),DARK_WOOD,"books")
    room.plant(994,420)
    return room.finish()


def computer_science():
    room = hall("computer_science", [(197,132),(945,132),(1098,215),(1098,559),(744,559),(744,603),(198,603)],
                (258,537),(719,301),(157,163,151),
                [("room.cs_display",(440,170)),("room.cs_study",(858,522))])
    window(room,225,144,680)
    room.wall((238,228,11,139),STEEL)
    room.fixture((298,197,298,54),STEEL)
    for i in range(7):
        pygame.draw.aaline(room.surface,GLASS,(335+i*30,211),(361+i*30,229))
    room.fixture((803,221,150,33),DARK_WOOD,"books")
    room.fixture((834,297,125,33),TEAL,"sofa")
    room.fixture((829,413,123,33),TEAL,"sofa")
    room.fixture((817,361,129,28),WOOD,"round")
    room.wall((630,389,15,154),STEEL)
    room.plant(1052,444)
    return room.finish()


def student_center():
    room = hall("student_center", [(157,131),(1094,131),(1094,614),(721,614),(721,546),(157,546)],
                (212,491),(478,354),(176,165,144),
                [("room.shuimu_stalls",(433,187)),("room.shuimu_services",(902,539))])
    window(room,189,142,481)
    room.wall((699,160,15,232),STEEL)
    room.wall((699,489,15,55),STEEL)
    for x, color in ((222, TEAL), (378, WOOD), (534, RUST)):
        room.fixture((x,223,117,32),color,"desk")
        pygame.draw.rect(room.surface,color,(x,211,117,8),border_radius=3)
    for x, y in ((304,349),(544,352),(301,431)):
        room.fixture((x,y,86,24),WOOD,"round")
        pygame.draw.circle(room.surface,TEAL,(x+22,y+34),8)
    room.fixture((810,185,220,38),TEAL,"desk")
    for x,y in ((806,277),(946,277),(806,391),(946,391)):
        room.fixture((x,y,86,27),STEEL,"books")
    steps(room,959,468,77)
    room.plant(1057,347)
    return room.finish()


def humanities():
    room = hall("humanities_building", [(152,218),(265,218),(265,103),(1067,103),(1109,227),(1109,555),
                                       (895,555),(895,602),(152,602)],
                (204,540),(703,352),(165,159,142),
                [("room.hss_display",(434,183)),("room.hss_reading",(905,499))])
    window(room,297,120,710)
    room.wall((607,161,15,146))
    room.wall((607,422,15,154))
    for x,y in ((347,223),(437,287),(341,426)):
        room.fixture((x,y,130,17),DARK_WOOD,"books")
    for x,y in ((731,207),(930,239),(775,388),(955,395)):
        room.fixture((x,y,93,45),WOOD,"desk")
        pygame.draw.circle(room.surface,TEAL,(x+24,y+58),8)
    room.fixture((927,543,113,24),DARK_WOOD,"books")
    room.plant(531,512)
    return room.finish()


def public_interiors():
    return (general_two(), general_three(), general_four(), engineering(), physics(), chemistry(),
            sports(), food_court(), ren(), shi(), li(), yi(), administration(), engineering_three(),
            computer_science(), student_center(), humanities())
