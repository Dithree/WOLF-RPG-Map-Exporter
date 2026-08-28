# WOLF RPG 地图导出工具 v1.1

<p align="center">
  🌐 Language: <a href="#zh">中文</a> · <a href="#en">English</a> · <a href="#ja">日本語</a>
</p>

<p align="center">
  <img src="preview.png" alt="Preview 预览" width="640">
</p>

---

<a name="zh"></a>
## 中文说明

一个完全离线的 **WOLF RPG Editor（ウディタ）地图渲染/导出工具**。无需打开编辑器即可把 `.mps` 地图渲染成图片，并支持把**地图层**与**事件层**分开导出。

- 支持含日文/中文文件名的素材，可在非英文路径下运行
- 界面支持 **中文 / 日本語 / English** 切换（顶部菜单 Language，自动检测系统语言）
- 本工具由 **DeepSeek-v4-flash** 制作完成（作者仅提供工作思路），可导出游戏地图用于资料整理或留念等
- 感谢 **夏拉** 制作的中文编辑器和收集的资料
  - 编辑器汉化发布贴：https://tieba.baidu.com/p/8466671485?fr=frs

**适用对象**：WOLF RPG Editor（ウディタ）制作的游戏，包括新编辑器（3.x，0x67 格式）和旧编辑器（2.x，0x65/0x66 格式）。

### 使用方法

1. 运行 `WOLF_RPG_地图导出工具v1.1.exe`。
2. 点击顶部 **「选择游戏(Data 文件夹)」**，选择游戏的 `Data` 文件夹（或包含 `MapData` 的目录）。
3. 左侧地图列表：勾选需要导出的地图，点击某个地图名可预览；可同时勾选多张。
4. 底部选择导出模式：
   - **事件层**：只导出事件层（透明背景），隐藏的事件不会出现在导出图里
   - **地图层**：只导出地图层
   - **两者**：地图层 + 可见事件层叠加
5. 点击 **「导出当前地图」** 可导出当前预览图；**「导出所选地图」** 选择导出文件夹，一次性导出所有已勾选地图（按所选模式）；**「复制到剪贴板」** 可把当前预览结果复制到剪贴板。

### 更新日志 v1.1

本工具历经数次完整逆向与修复，核心成果与修复记录如下：

- **地图格式解析**：解析 `.mps` 文件、三图层、事件区；支持 **0x65 / 0x66 / 0x67** 三种版本混用（0x67 为 LZ4 压缩格式）
- **图块渲染**：base 图块（raw=0 有效）；aid1 透明层（100000~199999 不绘制）；自动图块行规则（8 邻域 + 中心四位数字查表）；墙角规则（aid 感知，`aid;掩码;数字` 区分图块类型）
- **布局/尺寸**：非方形布局修复（`D[y][x]=flat[x*H+y]`）；任意尺寸正方形地图正确渲染
- **素材加载**：多语言文件名解析（cp932/shift-jis/utf-8/gbk/big5）；非英文路径支持
- **背景/图层**：支持地图背景图片（手动配置表，默认不启用）
- **事件层**：离线渲染事件层（透明背景）；单击事件切换显示/隐藏（隐藏=半透明），导出/复制时隐藏事件不显示

### 说明

- 本工具为完全离线渲染，不依赖 WOLF RPG Editor 本体。
- 渲染算法基于对 WOLF RPG Editor 引擎的反向工程，理论上适用于同一编辑器的所有游戏。
- 若遇到个别特殊图块/墙角仍不精确，可通过 **唯一色导出 + 自动收集规则** 流程扩充规则表（详见源码 `_rebuild_rule_table_aid.py`）。

**License**: MIT ｜ 版本：1.1

---

<a name="en"></a>
## English

A fully offline **WOLF RPG Editor (ウディタ) map renderer/exporter**. Renders `.mps` maps to PNG images without opening the editor, and can export the **map layer** and **event layer** separately.

- Supports assets with Japanese/Chinese filenames; runs in non-English paths
- In-app UI language switch: **Chinese / 日本語 / English** (top menu "Language", auto-detects system language)
- Made by **DeepSeek-v4-flash** (the author only provided the working ideas); use it to organize or archive game maps
- Thanks to **夏拉** for the Chinese editor and collected resources
  - Editor localization post: https://tieba.baidu.com/p/8466671485?fr=frs

**Supported targets**: games made with WOLF RPG Editor (ウディタ), including the new editor (3.x, 0x67 format) and old editor (2.x, 0x65/0x66 format).

### Usage

1. Run `WOLF_RPG_地图导出工具v1.1.exe`.
2. Click **「Select Game (Data folder)」** and choose the game's `Data` folder (or a directory containing `MapData`).
3. Left map list: check the maps to export; click a map name to preview; multiple maps can be checked at once.
4. Choose an export mode at the bottom:
   - **Event layer**: export only the event layer (transparent background); hidden events are excluded
   - **Map layer**: export only the map layer
   - **Both**: map layer + visible event layer
5. **「Export current map」** exports the current preview; **「Export selected maps」** exports all checked maps to a chosen folder (per the selected mode); **「Copy to clipboard」** copies the current result to the clipboard.

### Changelog v1.1

This tool went through complete reverse-engineering and many fixes:

- **Map format parsing**: parses `.mps`, three layers, event area; supports **0x65 / 0x66 / 0x67** mixed (0x67 is LZ4-compressed)
- **Tile rendering**: base tiles (raw=0 valid); aid1 transparent layer (100000~199999 not drawn); autotile row rule (8-neighbor mask + 4-digit center); corner rule (aid-aware, keyed by `aid;mask;digits`)
- **Layout / size**: non-square layout fix (`D[y][x]=flat[x*H+y]`); any-size square maps render correctly
- **Asset loading**: multi-language filename parsing (cp932/shift-jis/utf-8/gbk/big5); non-English path support
- **Background / layers**: optional map background image (manual config table, disabled by default)
- **Event layer**: offline event layer rendering (transparent); click an event to toggle show/hide (hidden = semi-transparent); hidden events excluded from export/copy

### Notes

- Fully offline rendering; does not depend on the WOLF RPG Editor itself.
- Rendering is based on reverse-engineering the WOLF RPG Editor engine; in principle it works for all games of the same editor.
- If some tiles/corners are still imprecise, extend the rule table via the **unique-color export + auto rule collection** workflow (see `_rebuild_rule_table_aid.py`).

**License**: MIT ｜ Version: 1.1

---

<a name="ja"></a>
## 日本語

WOLF RPG Editor（ウディタ）のマップを、エディタを開かずに **PNG 画像**として出力できる完全オフラインのマップ描画/出力ツールです。**マップ層**と**イベント層**を分けて出力できます。

- 日本語・中国語のファイル名の素材に対応し、非英語パスでも動作
- アプリ内の言語切替: **中文 / 日本語 / English**（上部メニュー「Language」、システム言語自動検出）
- **DeepSeek-v4-flash** が制作（作者は作業方針のみ提供）。ゲームマップの資料整理・記念保存などにどうぞ
- **夏拉** さんによる中国語エディタと資料収集に感謝
  - エディタ中文化スレッド: https://tieba.baidu.com/p/8466671485?fr=frs

**対応対象**: WOLF RPG Editor（ウディタ）製のゲーム。新エディタ（3.x、0x67 形式）と旧エディタ（2.x、0x65/0x66 形式）の両方に対応。

### 使い方

1. `WOLF_RPG_地图导出工具v1.1.exe` を実行。
2. 上部の **「ゲーム選択(Data フォルダ)」** をクリックし、ゲームの `Data` フォルダ（または `MapData` を含むフォルダ）を選択。
3. 左のマップ一覧で出力したいマップをチェック。マップ名クリックでプレビュー。複数チェック可能。
4. 下部で出力モードを選択:
   - **イベント層**: イベント層のみ出力（透明背景）。非表示にしたイベントは出力に含まれません
   - **マップ層**: マップ層のみ出力
   - **両方**: マップ層 + 表示中のイベント層
5. **「現在のマップを出力」** でプレビュー中のマップを出力。**「選択したマップを出力」** でチェックした全マップを選択フォルダへ一括出力。**「クリップボードにコピー」** で現在の結果をコピー。

### 更新履歴 v1.1

本ツールは完全なリバースエンジニアリングと多数の修正を経て完成しました:

- **マップ形式解析**: `.mps`・3レイヤー・イベント領域を解析。**0x65 / 0x66 / 0x67** の混在に対応（0x67 は LZ4 圧縮形式）
- **タイル描画**: base タイル（raw=0 有効）; aid1 透明レイヤー（100000~199999 は非描画）; オートタイル行規則（8近傍+中央4桁）; 角ルール（aid 対応、`aid;マスク;数字`）
- **レイアウト / サイズ**: 非正方形レイアウト修正（`D[y][x]=flat[x*H+y]`）; 任意サイズの正方形マップも正しく描画
- **素材読み込み**: 多言語ファイル名解析（cp932/shift-jis/utf-8/gbk/big5）; 非英語パス対応
- **背景 / レイヤー**: マップ背景画像に対応（手動設定テーブル、デフォルト無効）
- **イベント層**: オフライン描画（透明背景）; クリックで表示/非表示切替（非表示=半透明）; 出力/コピー時は非表示イベントを除外

### 補足

- 完全オフライン描画のため、WOLF RPG Editor 本体には依存しません。
- WOLF RPG Editor エンジンのリバースエンジニアリングに基づくため、原則として同一エディタの全ゲームに適用できます。
- 一部の特殊タイル・角が不正確な場合は、**ユニーク色出力 + 自動ルール収集**のフローで規則テーブルを拡充できます（詳細は `_rebuild_rule_table_aid.py`）。

**License**: MIT ｜ バージョン: 1.1
