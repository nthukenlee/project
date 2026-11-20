# 清華拾光：別跟著聲音走

清華大學新竹校本部題材的非官方 2D 校園生存冒險。劇情、角色及廣播設備均為虛構。

## 開始遊玩

下載此分支後，在專案資料夾用 Python 3.14 安裝依賴並啟動。Windows 若以預設位置安裝 Python，也可以雙擊 **Play-Latest.cmd**。

```powershell
python -m pip install -r requirements.txt
python main.py
```

| 按鍵 | 操作 |
| --- | --- |
| WASD／方向鍵 | 移動 |
| Shift（按住） | 跑步 |
| E／Enter | 閱讀、翻找、交談或進出建築 |
| 滑鼠點道具欄／1–6 | 選擇道具 |
| 空白鍵 | 使用目前道具 |
| B | 已取得自行車時，在室外騎車或下車 |
| M／Q | 地圖／調查筆記 |
| Esc／F11 | 暫停或返回／切換全螢幕 |

## 本版內容

- 遊戲從 17:42 開始，左上角顯示校園時間。17:48 停電。停電後接近這輪抽到的危機現場，或於 17:51 聽到異常廣播，就會引發感染爆發。感染者分三批進場。
- 20 棟可進入建築各有入口、家具、碰撞和事件。開新局時從 20 棟室內與 8 處戶外候選點抽出 5–8 個不同的主線地點，至少一站在戶外，臨時接應區在室內。比對錄音後，可以追查原始索引或核對備份並改走另一處；同伴可以省下核對時間。調查簽到紀錄後，可用額外時間搜找備用電池。M 地圖顯示目的地，Q 筆記顯示目前站數。
- 58 個室內及 20 個戶外候選事件。每局每棟建築抽一個事件，戶外再抽 8–12 個。角色、事件位置組合及新增戶外事件的出現時間由每局種子決定。感染爆發後才開放隨機事件，紀錄可從 Q 筆記查看。新增短程護送、扣上門閂、用聲響引開感染者及在食物與水之間選擇。查證會影響部分事件的結果。
- 目前有一個壞結局《名單上的最後一人》。舊版進行中的四站主線保留已抽中的路線與進度，也保留原有的事件紀錄。開新局會使用 5–8 站主線。
- 可切換繁體中文或英文。男女角色外觀有獨立的臉型、輪廓與衣裝，並可自訂名字、上衣、髮型、髮色和膚色。
- 每輪隨機配置五種感染者，爆發後期此外會出現伏行與重殼變種。口渴或飢餓歸零、被感染者咬中會結束本輪。NPC 也會感染並攻擊身邊的人。最多兩名同伴，主線可單人完成。感染者移速下調；近距離追兵能跟著穿過同一扇門，入場前會有撞門提示。突發驚嚇可從設定關閉。
- 下雨時戶外移速下降 20%，夜晚看得見近處，手電筒可延伸前方視野。每局有 40 份以上補給，分散藏在室內的抽屜、層架與收納櫃，球棒能短暫擊退感染者，揮動也會引來附近敵人。
- 活著可存檔繼續；死亡或結局會結束當前存檔。設定和角色外觀另外保存。Windows 存檔位於 `%LOCALAPPDATA%\NTHUPixelAdventure\last-report`。舊版的存檔另存副本供保留。
- 原創背景音樂持續循環，追逐、停電和結局以漸變切換曲目。對話與片頭以文字呈現，保留雨聲及操作音效。

## 室內參考

- 教育館依一樓平面圖安排西側入口、中庭與 113／115 的相對位置，115 地面、黑板與講桌參考課務組資料。室內動線有配合遊戲縮放。[一樓平面圖](https://thcollege.site.nthu.edu.tw/var/file/90/1090/img/397395079.pdf) · [115 教室](https://curricul.site.nthu.edu.tw/p/406-1208-210233,r1162.php?Lang=zh-tw)
- 旺宏館依後棟一樓導覽重畫斜向入口、聯合櫃臺、自助取書、知識集、輕學區與清沙龍。[旺宏館一樓導覽](https://www.lib.nthu.edu.tw/library/image/1F.jpg)
- 新齋採公開交誼廳照片的木地板、靠窗長桌、白圓桌、彩色座椅及深色沙發。公共走廊為遊戲中的簡化配置。[新齋公開照片](https://sthousing.site.nthu.edu.tw/p/404-1254-13727.php?Lang=zh-tw)
- 綜二與綜四以校方教室配置資料和公共服務機能為參考，工一使用 101 教室，綜三、物理館和化學館採教學公共空間的遊戲化配置。[課務組教室環境](https://curricul.site.nthu.edu.tw/p/404-1208-95066.php?Lang=zh-tw) · [工一 101](https://curricul.site.nthu.edu.tw/p/406-1208-10439,r1143.php?Lang=zh-tw) · [校本部導覽](https://www.nthu.edu.tw/campusmap)
- 體育館和小吃部分別以體育室館舍及餐飲店聚落為參考，重畫球場、休息席、並列餐檯和用餐座位。[體育室場館](https://my.nthu.edu.tw/~physical/placeView.html) · [校園生活](https://tcsl.site.nthu.edu.tw/p/412-1216-21928.php)
- 仁、實、禮、義齋以住宿組的交誼廳或服務區照片畫出可見家具和材質。各公共空間接合動線、捷徑及事件裝置使用遊戲尺度。[仁齋](https://sthousing.site.nthu.edu.tw/p/404-1254-13650.php?Lang=zh-tw) · [實齋](https://sthousing.site.nthu.edu.tw/p/404-1254-13681.php?Lang=zh-tw) · [禮齋](https://sthousing.site.nthu.edu.tw/p/404-1254-13683.php?Lang=zh-tw) · [義齋](https://sthousing.site.nthu.edu.tw/p/404-1254-13635.php?Lang=zh-tw)


- 新增行政大樓、工三、劉炯朗館、水木生活中心和人社院室內。服務臺、典藏展示、餐飲與分館閱覽等空間為公開資料啟發的遊戲化配置。[行政大樓](https://general.site.nthu.edu.tw/p/404-1004-265849.php?Lang=zh-tw) · [劉炯朗館](https://secretary.site.nthu.edu.tw/p/405-1070-267691%2Cc8330.php) · [水木生活中心](https://yushan.site.nthu.edu.tw/p/412-1518-17643.php?Lang=zh-tw) · [人社分館](https://www.lib.nthu.edu.tw/library/hslib/)

## 驗證

```powershell
python -m unittest discover -s tests -v
python main.py --smoke-test outputs/last-report-smoke/report.json
```

以 `build_windows.ps1` 可將新版封裝為 Windows 視窗版 EXE。校園外部參考沿用 [MAP_REFERENCE.md](MAP_REFERENCE.md)。
