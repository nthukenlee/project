# 清華拾光 · 2D 手繪漫遊（v5）

Python / pygame-ce 校園探索遊戲。v5 改為原生 1280×720 的非像素 2D 手繪呈現，使用平面地景、正面建築立面、水彩植物與自然材質；已移除舊版斜視場景、像素渲染、地上發光物、自動撿取、隱藏道具、素材採集及製作流程。

## 下載與執行

此儲存庫包含遊戲原始碼、必要美術素材、資料、測試與文件，不包含 Windows EXE、ZIP、開發快取或玩家存檔。建議使用 Windows、Python 3.14 與依賴檔指定的 pygame-ce 版本。

```powershell
git clone https://github.com/nthukenlee/project.git
cd project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

標題選「從宿舍區開始」可直接看到改版的仁齋，按 C 查看四棟宿舍的建築導覽。已有桌面交付版的使用者，也可直接開啟「清華拾光-2D手繪版-v5.exe」。

## 操作

| 功能 | 操作 |
|---|---|
| 移動 / 跑步 | WASD、方向鍵 / Shift |
| 交談、進入建築、使用室內設施 | E 或 Enter |
| 校園地圖與目的地移動 | M，點選建築或右側目的地 |
| 任務與觀察手札 | Q |
| 仁、實、禮、義齋建築導覽 | C |
| 選擇下方功能 | 1–6 |
| 使用所選功能 | Space；也可直接點按鈕 |
| 單車 | B |
| 暫停 / 離開室內 | Esc |
| 全螢幕 | F11 |

下方功能列為地圖、手札、相機、飲水、餐點與單車。飲水與餐點來自餐廳、補水點及初始補給，沒有地上撿取。相機只記錄觀察，不會產生掉落物或可交易道具。

## 目前內容

- 160×112 格校園、12 個區域、26 棟可進入建築、15 位 NPC。
- 8 條走訪、訪談與校園觀察任務；結局進度不需要收集物品。
- 可自訂角色名稱與外觀，保留飢餓、口渴、體力、時間、單車、拍攝和室內互動。
- 仁、實、禮、義齋各自有不同 2D 立面，依清大住宿組官方照片核對面磚、窗型、弧形窗帶、入口階梯及扶手等特徵。
- 宿舍房間依官方仁齋四人房照片的「兩側上鋪及書桌、中央走道」重繪；其他宿舍室內共用此示意配置，尚未逐棟逐房實測還原。
- 繁中 / 英文、視窗縮放 / 全螢幕、自動存檔和三個手動存檔槽。

宿舍立面是有來源的遊戲化重繪，遮蔽面、建築深度及其他校園建築並非精準測繪還原。校園位置沿用遊戲地圖，不能作為真實導航。這次是美術與玩法改版，不表示原訂 60–90 分鐘完整內容已驗收。

## 原始碼執行與測試

```powershell
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
python main.py --smoke-test outputs/smoke/report.json
```

測試涵蓋移除的撿拾機制、全部任務完成、宿舍來源資料、碰撞可達性、室內互動、雙語場景、存檔往返與舊存檔遷移。

```powershell
python -m pip install -r requirements-dev.txt
.\build_windows.ps1
```

打包輸出為 `outputs/NTHUWalk2D.exe`，交付時改為上述中文檔名。

## 存檔與 Git

沿用 `%LOCALAPPDATA%\NTHUPixelAdventure` 以讀取舊存檔。載入時保留角色、任務、探索和照片，移除已取消的收藏、素材、製作物與舊場景狀態；不刪除原始存檔檔案。

Git 記錄程式、資料、素材及文件；`.gitignore` 排除執行檔、封裝檔、預覽圖、快取、環境與測試產物。素材來源與美術限制見 [ATTRIBUTIONS.md](ATTRIBUTIONS.md) 及 [美術規格](assets/ART_DIRECTION_V5.md)。
