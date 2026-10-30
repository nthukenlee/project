# Sources and notices — hand-painted 2D v7

This is an unofficial project, not endorsed by National Tsing Hua University.

## Architectural references

The following NTHU Student Housing Division pages and their official exterior photographs were inspected for facade identity. Reference photos are not distributed in the game; only project-specific hand-painted redraws are bundled.

- Ren Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13650.php?Lang=zh-tw
- Shi Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13681.php?Lang=zh-tw
- Li Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13683.php?Lang=zh-tw
- Yi Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13635.php?Lang=zh-tw
- Xin Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13727.php?Lang=zh-tw
- Campus spatial background: https://www.nthu.edu.tw/campusmap

`data/dorm_architecture.json` records individual photo URLs and visible features. Ren's four visible residential window rows are explicitly reconstructed by the 2D facade renderer because the generated base image omitted one row. Shi's partially hidden exterior is not assigned an unverified total floor count. Shared dorm-room layouts are based on the official Ren four-person room photo, not claimed as verified plans for all halls.

## Art and code

The fourteen images in `assets/painted/` were produced for this project with OpenAI's built-in image generation tool. Prompts requested non-pixel ink/watercolor, matte materials and architectural elevations. See `assets/ART_DIRECTION_V5.md`, `assets/ART_DIRECTION_V6.md` and `assets/ART_DIRECTION_V7.md` for paths and specifications. Runtime animation, colors, facade assembly, navigation, tasks, interface and original synthesized sound cues are implemented in Python. Some cutouts retain shallow side views; the game uses 2D surfaces, without a 3D scene or models.

## Campus Green, north gate and individual buildings (v7)

- Official campus guide and building markers/photos: https://campusmap.cc.nthu.edu.tw/ and https://campusmap.cc.nthu.edu.tw/xml/Markersite.xml
- Education Hall: https://attractions.site.nthu.edu.tw/p/406-1515-186971,r8697.php?Lang=zh-tw
- General IV (formerly R&D Building): https://attractions.site.nthu.edu.tw/p/406-1515-186944,r8697.php?Lang=zh-tw
- Campus Green location: https://affairs.site.nthu.edu.tw/p/406-1165-56561,r3514.php?Lang=zh-tw
- North gate renovation: https://www.lib.nthu.edu.tw/events/2023/scenery/index.html
- Physics building, architect's reference: https://www.cylee.com/project/Department-of-Physics-nthu?lang=tw
- Tsing Hua Laboratory: https://www.nthu.edu.tw/hotNews/content/636

`data/campus_architecture.json` identifies the individual reference photo, crop and visible features of 29 non-dorm buildings. Twenty-eight use seven original generated atlases; Tsing Hua Laboratory uses a dedicated original Python elevation. Five dorms retain their separate reference data and artwork. General IV and its old R&D name share one destination; Liu Jiong Lang Hall and its former generic information/electrical destination are consolidated. No raw reference photos are included in release assets. Elevations are interpretive redraws, not measured facades; room layouts remain schematic. Coverage is the 34 modeled buildings, not every campus building or path.

## Roads and Success Lake (v6)

- NTHU campus road plan and road names: https://commencement.site.nthu.edu.tw/var/file/583/1583/img/4983/802873434.pdf (official university publication; includes the 111.12 road plan).
- Success Lake renovation layout, bridge/island names and waterfront spaces: https://www.lib.nthu.edu.tw/events/2026/history/present.html
- Supporting campus landscape history: https://attractions.site.nthu.edu.tw/p/406-1515-186930,r11.php?Lang=zh-tw

Road polylines and water polygons were manually authored with these references. Original official map graphics, aerial images and photographs are not bundled with the game. Small access paths, facade footprints, lake proportions and walking distances are adjusted to support the 2D game; see `MAP_REFERENCE.md` for scope and limitations. The v6 map consolidates the duplicate General I / Administration destination and adds Xin Hall. Room plans remain schematic; Xin A/B/C wings share one entrance.

The old pixel sprites and perspective scene images have been removed from the working project. Git retains recoverable history. No art, character or code is taken from Stardew Valley, Minecraft or Terraria.

Python source is MIT licensed. pygame-ce uses LGPL 2.1; PyInstaller is a build tool with its application bundling exception. Real building names are descriptive references. The campus layout is stylized and must not be used for navigation.
