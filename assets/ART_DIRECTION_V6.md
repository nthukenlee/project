# v6 新齋立面素材

生成方式：OpenAI 內建 `image_gen` 工具。參考清大住宿組新齋外觀照片，生成原創非像素、平行正面立面；沒有將官方照片分發為遊戲素材。

遊戲素材：`assets/painted/xin-facade-v6.png`。官方參考、可見特徵及尺度限制另記在 `data/dorm_architecture.json` 與 `MAP_REFERENCE.md`。生成圖保留透明背景。使用於戶外地圖、宿舍導覽及標題畫面。

## 最終提示詞

Use case: illustration-story. Asset type: original 2D campus game building cutout. Reference image: official NTHU Xin Hall exterior photograph, ONLY for architectural identity. Generate an original full orthographic FRONT ELEVATION of the central Xin Hall facade plus symmetric wings, NO perspective, NO isometric, NO 3D rendering. Matte ink-and-watercolor illustration with subtle fine tile grain, restrained muted natural sage, grey cream and dusty brown palette; smoothly painted NON PIXEL artwork. Preserve characteristic pale grey small-tile vertical piers, tall recessed dusty brown vertical window bays with small silver external AC boxes, 8 visible rows of residential windows, open corridor balcony stack in center with softly curved balcony fronts, one large circular opening above the central ground entry and small gable with round vent at the top. The photo shows wings converging due to perspective; flatten to a parallel elevation, centered and horizontally spread. Ground entry clearly visible at bottom center. Transparent background, isolated whole facade only, 5% safe margins, no trees, no people, no pavement, no sky, NO text, no logo, no watermark. Architectural detail and authored watercolor texture, not glossy plastic, no bevelled cartoon assets.

這張立面著重照片可見特徵；生成的窗列與翼部為遊戲化展開，未據此宣稱實際總樓層或完整建築尺寸。現有六張 v5 素材繼續使用，規格見 `ART_DIRECTION_V5.md`。道路、橋、湖岸與水面均由 Python 依資料繪製，未新增外部貼圖。
