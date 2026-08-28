# WOLF RPG Map Exporter v1.1

<p align="center">
  🌐 Language: <a href="README.md">中文</a> · <b>English</b> · <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img src="preview.png" alt="Preview" width="640">
</p>

A fully offline **WOLF RPG Editor (ウディタ) map renderer/exporter**. Renders `.mps` maps to PNG images without opening the editor, and can export the **map layer** and **event layer** separately.

- Supports assets with Japanese/Chinese filenames; runs in non-English paths
- In-app UI language switch: **Chinese / 日本語 / English** (top menu "Language")
- Made by **DeepSeek-v4-flash** (the author only provided the working ideas); use it to organize or archive game maps
- Thanks to **夏拉** for the Chinese editor and collected resources
  - Editor localization post: https://tieba.baidu.com/p/8466671485?fr=frs

**Supported targets**: games made with WOLF RPG Editor (ウディタ), including the new editor (3.x, 0x67 format) and old editor (2.x, 0x65/0x66 format).

---

## Usage

1. Run `WOLF_RPG_地图导出工具v1.1.exe`.
2. Click **「Select Game (Data folder)」** and choose the game's `Data` folder (or a directory containing `MapData`).
3. Left map list: check the maps to export; click a map name to preview; multiple maps can be checked at once.
4. Choose an export mode at the bottom:
   - **Event layer**: export only the event layer (transparent background); hidden events are excluded
   - **Map layer**: export only the map layer
   - **Both**: map layer + visible event layer
5. **「Export current map」** exports the current preview; **「Export selected maps」** exports all checked maps to a chosen folder (per the selected mode); **「Copy to clipboard」** copies the current result to the clipboard.

---

## Changelog v1.1

This tool went through complete reverse-engineering and many fixes:

### Map format parsing
- Parses `.mps` files, three layers, and the event area
- Supports **0x65 / 0x66 / 0x67** mixed (0x67 is LZ4-compressed)

### Tile rendering
- **Base tiles**: raw=0 is a valid base tile (first cell); fixes missing tiles such as id32
- **aid1 transparent layer**: 100000~199999 treated as transparent, not drawn
- **Autotile row rule**: lookup by 8-neighbor mask + 4-digit center; supports any layer (0/1/2)
- **Corner rule (aid-aware)**: rule table keyed by `aid;mask;digits` distinguishes autotile types; fixes walls interfering and corners turning transparent

### Layout / size
- **Non-square layout fix**: applies `D[y][x]=flat[x*H+y]` for both 0x67 and 0x65/0x66 non-square maps
- Square maps of any size (10×10 / 20×20 / 30×30) render correctly

### Asset loading
- **Multi-language filename parsing**: keeps raw bytes and tries cp932 / shift-jis / utf-8 / gbk / big5 to match real files; fixes mojibake for Japanese/Chinese names
- **Non-English path support**: uses Unicode paths throughout

### Background / layers
- Optional map background image (manual config table; disabled by default to stay generic)

### Event layer
- Offline event layer rendering (transparent background) for chara/tile events and shadows
- Fixes blank event layers by using the real Data directory for `CharaChip`/`MapChip` assets
- Click an event in preview to toggle show/hide (hidden = semi-transparent); hidden events are excluded from export

---

## Notes

- Fully offline rendering; does not depend on the WOLF RPG Editor itself.
- Rendering is based on reverse-engineering the WOLF RPG Editor engine; in principle it works for all games of the same editor.
- If some tiles/corners are still imprecise, extend the rule table via the **unique-color export + auto rule collection** workflow (see `_rebuild_rule_table_aid.py`).
