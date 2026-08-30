extends Control

## 中文像素字体的实机可读性对比（ART-2）。
##
## 它要回答的只有一个问题：**10px 的中文在实机上看不看得清。**
## 玩法定位那张分辨率推算表是按 12px 估的，10px 从没实测过；如果 10px 能用，
## 320×180 可能重回候选，而那会连带影响 UI-1。
##
## 两种用法：
##   <godot> --path .            交互看：←→ 换字体，1/2/3 换逻辑分辨率，+/- 换缩放，S 存图
##   <godot> --path . -- --shots 自动出图后退出（每个「分辨率 × 字体」一张，外加一张对比总表）
##
## 三条刻意的做法：
##   1. 字体在运行时用 load_dynamic_font 读，绕开导入管线 —— 那样每个像素完美选项都
##      写在这份脚本里看得见，而不是藏在 .import 文件的默认值里。
##   2. 每个选项先探属性表再设，设不上的记下来。Godot 各版本这些属性改过名，
##      闷头 set() 会静默失效，而字变糊时你只会怀疑字体。
##   3. 字号一律等于字体的设计尺寸（em/100），并打出实测的字宽与行高。
##      对不上就说明像素完美没成立，不靠目测。

const FONTS := [
	{"id": "fusion-12", "name": "缝合像素 12px", "size": 12,
	 "path": "fusion-12px/fusion-pixel-font-12px-proportional-ttf-v2026.08.11/fusion-pixel-12px-proportional-zh_hans.ttf"},
	{"id": "fusion-10", "name": "缝合像素 10px", "size": 10,
	 "path": "fusion-10px/fusion-pixel-font-10px-proportional-ttf-v2026.08.11/fusion-pixel-10px-proportional-zh_hans.ttf"},
	{"id": "fusion-8", "name": "缝合像素 8px", "size": 8,
	 "path": "fusion-8px/fusion-pixel-font-8px-proportional-ttf-v2026.08.11/fusion-pixel-8px-proportional-zh_hans.ttf"},
	{"id": "cubic-11", "name": "Cubic 11 繁体向", "size": 12,
	 "path": "cubic-11/Cubic_11.ttf"},
]

const RESOLUTIONS := [Vector2i(320, 180), Vector2i(480, 270), Vector2i(640, 360)]

# 占位配色。**正式界面色板归 DOC-2，本工程不产出色板结论。**
const BG := Color8(0x21, 0x1A, 0x17)        # 暖炭底
const PANEL := Color8(0x33, 0x28, 0x22)     # 对话框底
const EDGE := Color8(0x6B, 0x52, 0x3C)      # 对话框边
const INK := Color8(0xEA, 0xDF, 0xC8)       # 正文
const DIM := Color8(0x9A, 0x8B, 0x74)       # 次要信息
const HOT := Color8(0xE0, 0x9A, 0x4E)       # 强调

const SPEAKER := "教官 · 芜"
const DIALOGUE := "明天出征前，把这批药剂分给三名学员 —— 别让谁空着手上前线。回来时我要看到四个人，不是三个。"
const HUD := "体力 78/120　星火 3　第 12 天　春　07:20"
const LIST := ["炭化木材 ×24", "锈铁碎片 ×8", "净水滤芯 ×1"]
# 故意混进两个生僻字与一批标点：缺字在这里显成豆腐块，而不是等上线被玩家发现。
const EDGES := "晫缁　「」『』《》【】—…※　0123456789　ABCdef"

var _fonts: Array[Dictionary] = []
var _font_i := 0
var _res_i := 1
var _scale := 3
var _sheet_mode := false
var _sheet_size := Vector2i(480, 240)
var _measured := {}
var _log: PackedStringArray = []
## 拉伸模式。`viewport` 先画逻辑分辨率再整数放大；`canvas_items` 按最终屏幕尺寸画字形。
## 两者对像素字的结果不同，这正是 `UI-4` 要量的东西。
var _stretch_canvas := false


func _ready() -> void:
	var audit := ProjectSettings.globalize_path("res://").path_join("../font-audit").simplify_path()
	_say("字体来源目录 %s" % audit)
	for spec in FONTS:
		var font := _make_font(audit.path_join(spec["path"]), spec["name"])
		if font != null:
			var entry: Dictionary = spec.duplicate()
			entry["font"] = font
			_fonts.append(entry)
			_measure(entry)
	if _fonts.is_empty():
		_say("[FAIL] 一个字体都没载入 —— 先在设计仓跑 python tools/audit_fonts.py 下字体")
		_flush()
		get_tree().quit(1)
		return

	var args := OS.get_cmdline_user_args()
	_stretch_canvas = "--canvas-items" in args
	if "--linear-filter" in args:
		# 反证用：把本节点的纹理过滤改成线性。字形图集被画布变换放大时若走线性插值，
		# 边缘会出现渐变像素，最小同色跑长应当掉到 1。
		texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
		_say("[反证] 本次纹理过滤改为线性")
	_say("拉伸模式 %s" % ("canvas_items" if _stretch_canvas else "viewport"))

	_apply_window()
	if "--measure" in args:
		await _measure_pixel_blocks()
		_flush()
		get_tree().quit(0)
		return
	if "--shots" in args:
		await _shoot_all()
		_flush()
		get_tree().quit(0)


## 建字体。每个像素完美选项都先探属性表再设，设不上的记进日志。
func _make_font(path: String, label: String) -> FontFile:
	if not FileAccess.file_exists(path):
		_say("[FAIL] %s 找不到文件：%s" % [label, path])
		return null
	var font := FontFile.new()
	var err := font.load_dynamic_font(path)
	if err != OK:
		_say("[FAIL] %s 载入失败（错误码 %d）：%s" % [label, err, path])
		return null

	var wanted := {
		"antialiasing": TextServer.FONT_ANTIALIASING_NONE,
		"hinting": TextServer.HINTING_NONE,
		"subpixel_positioning": TextServer.SUBPIXEL_POSITIONING_DISABLED,
		"multichannel_signed_distance_field": false,
		"generate_mipmaps": false,
		"force_autohinter": false,
		"allow_system_fallback": false,
		"disable_embedded_bitmaps": true,
		"keep_rounding_remainders": false,
		"oversampling": 1.0,
	}
	# 反证用：故意不钉 oversampling，看像素块会不会塌。见 _measure_pixel_blocks 的注释。
	if "--loose-oversampling" in OS.get_cmdline_user_args():
		wanted.erase("oversampling")
		_say("  [反证] 本次**不设** oversampling，看块状会不会塌")

	var have := {}
	for prop in font.get_property_list():
		have[prop["name"]] = true
	var applied: PackedStringArray = []
	var absent: PackedStringArray = []
	for key in wanted:
		if have.has(key):
			font.set(key, wanted[key])
			applied.append("%s=%s" % [key, font.get(key)])
		else:
			absent.append(key)
	_say("%s ← %s" % [label, path.get_file()])
	_say("  设上了：%s" % ", ".join(applied))
	_say("  这个版本没有的属性：%s" % (", ".join(absent) if absent.size() > 0 else "无"))
	return font


## 实测字宽与行高。像素完美的判据是「整数」，不是「看着还行」。
func _measure(entry: Dictionary) -> String:
	var key: String = entry["id"]
	if _measured.has(key):
		return _measured[key]
	var font: FontFile = entry["font"]
	var size: int = entry["size"]
	var han := font.get_string_size("汉", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var latin := font.get_string_size("A", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var height := font.get_height(size)
	var text := "字号 %d｜汉字宽 %.2f｜西文宽 %.2f｜行高 %.2f｜ascent %.2f" % [
		size, han, latin, height, font.get_ascent(size)]
	_measured[key] = text
	var integral := is_equal_approx(han, roundf(han)) and is_equal_approx(height, roundf(height))
	_say("  实测 %s → %s" % [text, "整数网格成立" if integral else "**不是整数，像素完美不成立**"])
	return text


func _apply_window() -> void:
	var res: Vector2i = _sheet_size if _sheet_mode else RESOLUTIONS[_res_i]
	var win := get_window()
	win.content_scale_mode = (Window.CONTENT_SCALE_MODE_CANVAS_ITEMS if _stretch_canvas
		else Window.CONTENT_SCALE_MODE_VIEWPORT)
	win.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
	win.content_scale_stretch = Window.CONTENT_SCALE_STRETCH_INTEGER
	win.content_scale_size = res
	win.size = res * (2 if _sheet_mode else _scale)
	queue_redraw()


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match (event as InputEventKey).keycode:
		KEY_RIGHT:
			_font_i = (_font_i + 1) % _fonts.size()
			queue_redraw()
		KEY_LEFT:
			_font_i = (_font_i - 1 + _fonts.size()) % _fonts.size()
			queue_redraw()
		KEY_1, KEY_2, KEY_3:
			_res_i = (event as InputEventKey).keycode - KEY_1
			_apply_window()
		KEY_EQUAL, KEY_KP_ADD:
			_scale = mini(_scale + 1, 6)
			_apply_window()
		KEY_MINUS, KEY_KP_SUBTRACT:
			_scale = maxi(_scale - 1, 1)
			_apply_window()
		KEY_F:
			_toggle_fullscreen()
		KEY_S:
			await _shoot_current()
		KEY_ESCAPE:
			_flush()
			get_tree().quit(0)


## 全屏才是成品的样子：整数拉伸会自己挑「塞得下的最大整数倍」，剩下的留黑边。
## 窗口模式下按 ×3 看，跟成品在同一台显示器上的观感不是一回事 —— 判可读性要用这个。
func _toggle_fullscreen() -> void:
	var win := get_window()
	var full := win.mode == Window.MODE_FULLSCREEN or win.mode == Window.MODE_EXCLUSIVE_FULLSCREEN
	win.mode = Window.MODE_WINDOWED if full else Window.MODE_FULLSCREEN
	await get_tree().process_frame
	var res: Vector2i = _sheet_size if _sheet_mode else RESOLUTIONS[_res_i]
	var got := win.size
	_say("窗口 %dx%d｜逻辑 %dx%d｜实际整数倍 ×%d（%s）" % [
		got.x, got.y, res.x, res.y,
		mini(got.x / res.x, got.y / res.y),
		"全屏" if not full else "窗口"])
	queue_redraw()


func _draw() -> void:
	if _sheet_mode:
		_draw_sheet()
	else:
		_draw_page()


func _draw_page() -> void:
	var res: Vector2i = RESOLUTIONS[_res_i]
	var entry: Dictionary = _fonts[_font_i]
	var font: FontFile = entry["font"]
	var size: int = entry["size"]
	var line := int(round(font.get_height(size)))

	draw_rect(Rect2(Vector2.ZERO, res), BG, true)

	var y := 2
	_line(font, size, 4, y, "%dx%d ×%d　%s" % [res.x, res.y, _scale, entry["name"]], HOT)
	y += line
	_line(font, size, 4, y, _measure(entry), DIM)
	y += line + 2
	_line(font, size, 4, y, HUD, INK)
	y += line + 2
	for item in LIST:
		_line(font, size, 4, y, item, INK)
		y += line
	y += 2
	_line(font, size, 4, y, EDGES, DIM)

	# 对话框占 80% 宽、贴底 —— 这是分辨率推算表里那个「约 N 字／行」的实际形状。
	var box_w := int(res.x * 0.8)
	var box_h := line * 4 + 8
	var box := Rect2(int((res.x - box_w) / 2.0), res.y - box_h - 4, box_w, box_h)
	draw_rect(box, PANEL, true)
	draw_rect(box, EDGE, false, 1.0)
	var tx := int(box.position.x) + 4
	var ty := int(box.position.y) + 4
	_line(font, size, tx, ty, SPEAKER, HOT)
	draw_multiline_string(font, Vector2(tx, ty + line + int(round(font.get_ascent(size)))),
		DIALOGUE, HORIZONTAL_ALIGNMENT_LEFT, box_w - 8, size, 3, INK)


## 一张总表：同一句话在四款字体下逐行排开，1 倍原生像素。
## 分辨率只决定一行装几个字；字形本身好不好认，在这张图上比。
func _draw_sheet() -> void:
	draw_rect(Rect2(Vector2.ZERO, _sheet_size), BG, true)
	var y := 2
	for entry in _fonts:
		var font: FontFile = entry["font"]
		var size: int = entry["size"]
		var line := int(round(font.get_height(size)))
		var han := int(font.get_string_size("汉", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x)
		_line(font, size, 4, y, "%s　汉字宽 %d　行高 %d" % [entry["name"], han, line], HOT)
		y += line
		_line(font, size, 4, y, DIALOGUE.substr(0, 26), INK)
		y += line
		_line(font, size, 4, y, HUD + "　" + EDGES.substr(0, 8), DIM)
		y += line + 4


func _sheet_height() -> int:
	var h := 4
	for entry in _fonts:
		h += int(round((entry["font"] as FontFile).get_height(entry["size"]))) * 3 + 4
	return h


func _line(font: FontFile, size: int, x: int, y: int, text: String, color: Color) -> void:
	# 基线取整：非整数基线会让像素字出现半像素模糊，而那看起来像「字体不行」。
	draw_string(font, Vector2(x, y + int(round(font.get_ascent(size)))), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, size, color)


func _out_dir() -> String:
	var dir := ProjectSettings.globalize_path("res://out")
	DirAccess.make_dir_recursive_absolute(dir)
	return dir


func _shoot_current() -> void:
	await RenderingServer.frame_post_draw
	var res: Vector2i = _sheet_size if _sheet_mode else RESOLUTIONS[_res_i]
	var file_name := "sheet.png" if _sheet_mode else "%dx%d-%s.png" % [
		res.x, res.y, _fonts[_font_i]["id"]]
	var img := get_viewport().get_texture().get_image()
	img.save_png(_out_dir().path_join(file_name))
	_say("存图 %s（%dx%d 原生像素）" % [file_name, img.get_width(), img.get_height()])


func _shoot_all() -> void:
	for ri in RESOLUTIONS.size():
		_res_i = ri
		_apply_window()
		for fi in _fonts.size():
			_font_i = fi
			queue_redraw()
			await RenderingServer.frame_post_draw
			await _shoot_current()
	_sheet_mode = true
	_sheet_size = Vector2i(480, _sheet_height())
	_apply_window()
	await RenderingServer.frame_post_draw
	await _shoot_current()
	_sheet_mode = false


## 量像素块边长（`UI-4`）。
##
## 判据不是"看着像块状"，而是**最小连续同色跑长必须等于缩放倍数**。12px 的字在 ×3 下若
## 仍是块状，每个字形像素都摊成 3×3，那么任意一行里最短的一段同色像素也是 3；一旦字形被
## 按 36px 重新光栅化，就会出现 1 到 2 像素宽的笔画，最小跑长立刻掉下来。
##
## 只量 canvas_items：viewport 模式下"先画小图再整数放大"是模式本身保证的，没什么可量。
func _measure_pixel_blocks() -> void:
	for scale in [2, 3, 4]:
		_scale = scale
		_font_i = 0                     # 固定用 12px 那款
		_apply_window()
		queue_redraw()
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		var res: Vector2i = RESOLUTIONS[_res_i]
		var expect := Vector2i(res.x * scale, res.y * scale) if _stretch_canvas else res
		var min_run := _min_color_run(img)
		var verdict := "块状（每个字形像素摊成 %d×%d）" % [scale, scale] if min_run == scale \
			else "**不是块状** —— 最小跑长 %d，字形没整块摊开（被插值或按最终尺寸重画）" % min_run
		_say("[量] 模式 %s｜缩放 x%d｜取回图 %dx%d（期望 %dx%d）｜最小同色跑长 %d → %s" % [
			"canvas_items" if _stretch_canvas else "viewport", scale,
			img.get_width(), img.get_height(), expect.x, expect.y, min_run, verdict])


## 扫全图每一行，取「非背景色的连续同色段」里最短的那个长度。
func _min_color_run(img: Image) -> int:
	var w := img.get_width()
	var h := img.get_height()
	var best := w
	var scanned := 0
	for y in range(0, h):
		var run := 0
		var prev := Color(0, 0, 0, 0)
		for x in range(w):
			var c := img.get_pixel(x, y)
			if x > 0 and c.is_equal_approx(prev):
				run += 1
				continue
			# 段结束：只统计非背景段，且不含贴左右边界的段（它们可能被裁断）
			if run > 0 and not prev.is_equal_approx(BG) and x - run > 0:
				best = mini(best, run)
				scanned += 1
			run = 1
			prev = c
	_say("  扫描 %d 行，统计到 %d 段非背景像素" % [h, scanned])
	return best


func _say(text: String) -> void:
	print(text)
	_log.append(text)


## 日志自己写 UTF-8 落盘，不靠管道读中文（设计仓 reference/踩坑记录.md 第 27 条）。
func _flush() -> void:
	var f := FileAccess.open(_out_dir().path_join("font-compare.log"), FileAccess.WRITE)
	if f != null:
		f.store_string("\n".join(_log) + "\n")
		f.close()
