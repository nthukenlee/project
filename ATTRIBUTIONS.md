# Sources and notices — hand-painted 2D v5

This is an unofficial project, not endorsed by National Tsing Hua University.

## Architectural references

The following NTHU Student Housing Division pages and their official exterior photographs were inspected for facade identity. Reference photos are not distributed in the game; only project-specific hand-painted redraws are bundled.

- Ren Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13650.php?Lang=zh-tw
- Shi Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13681.php?Lang=zh-tw
- Li Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13683.php?Lang=zh-tw
- Yi Hall: https://sthousing.site.nthu.edu.tw/p/404-1254-13635.php?Lang=zh-tw
- Campus spatial background: https://www.nthu.edu.tw/campusmap

`data/dorm_architecture.json` records individual photo URLs and visible features. Ren's four visible residential window rows are explicitly reconstructed by the 2D facade renderer because the generated base image omitted one row. Shi's partially hidden exterior is not assigned an unverified total floor count. Shared dorm-room layouts are based on the official Ren four-person room photo, not claimed as verified plans for all halls.

## Art and code

The six images in `assets/painted/` were produced for this project with OpenAI's built-in image generation tool. Prompts requested non-pixel ink/watercolor, matte materials, parallel architectural elevations and no 3D model rendering. See `assets/ART_DIRECTION_V5.md` for paths and specifications. Runtime animation, colors, facade assembly, navigation, tasks, interface and original synthesized sound cues are implemented in Python.

The old pixel sprites and perspective scene images have been removed from the working project. Git retains recoverable history. No art, character or code is taken from Stardew Valley, Minecraft or Terraria.

Python source is MIT licensed. pygame-ce uses LGPL 2.1; PyInstaller is a build tool with its application bundling exception. Real building names are descriptive references. The campus layout is stylized and must not be used for navigation.
