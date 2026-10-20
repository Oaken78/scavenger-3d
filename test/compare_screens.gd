extends SceneTree
## Headless screenshot comparison, run by tools/shots.ps1:
##   godot --headless --path <proj> -s res://test/compare_screens.gd -- --shots=<dir> --baselines=<dir>
##          --report=<file> --prefix=<scenario> [--threshold=0.02]
## For every <shot>.png in --shots, compares with <baselines>/<prefix>__<shot>.png using
## Image.compute_image_metrics (root_mean_squared). Writes a JSON report with SAME / CHANGED / NEW / MISSING / ERROR
## and a <shot>__diff.png (red = differing pixels) for CHANGED shots.


func _init() -> void:
	var shots := ""
	var baselines := ""
	var report := ""
	var prefix := ""
	var threshold := 0.02
	for a: String in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			shots = a.trim_prefix("--shots=")
		elif a.begins_with("--baselines="):
			baselines = a.trim_prefix("--baselines=")
		elif a.begins_with("--report="):
			report = a.trim_prefix("--report=")
		elif a.begins_with("--prefix="):
			prefix = a.trim_prefix("--prefix=")
		elif a.begins_with("--threshold="):
			threshold = float(a.trim_prefix("--threshold="))
	var results: Array = []
	var seen := {}
	var dir := DirAccess.open(shots)
	if dir == null:
		_write(report, {"error": "cannot open shots dir %s" % shots, "results": []})
		quit(2)
		return
	var base_prefix := prefix + "__" if not prefix.is_empty() else ""
	for file: String in dir.get_files():
		if not file.ends_with(".png") or file.ends_with("__diff.png"):
			continue
		var shot_name := file.get_basename()
		seen[shot_name] = true
		var base_name := base_prefix + shot_name + ".png"
		var base_path := baselines.path_join(base_name)
		var entry := {
			"shot": shot_name, "baseline": base_name, "status": "NEW", "rmse": -1.0, "diff": ""
		}
		if FileAccess.file_exists(base_path):
			var a := Image.load_from_file(shots.path_join(file))
			var b := Image.load_from_file(base_path)
			if a == null or b == null:
				entry["status"] = "ERROR"
				entry["detail"] = "could not load image"
			elif a.get_size() != b.get_size():
				entry["status"] = "CHANGED"
				entry["detail"] = "size %s vs baseline %s" % [a.get_size(), b.get_size()]
			else:
				if a.get_format() != b.get_format():
					b.convert(a.get_format())
				var m := a.compute_image_metrics(b, false)
				var rmse := float(m.get("root_mean_squared", 1.0))
				entry["rmse"] = snappedf(rmse, 0.000001)
				entry["max"] = snappedf(float(m.get("max", 0.0)), 0.000001)
				if rmse <= threshold:
					entry["status"] = "SAME"
				else:
					entry["status"] = "CHANGED"
					var diff_path := shots.path_join(shot_name + "__diff.png")
					_write_diff(a, b, diff_path)
					entry["diff"] = diff_path
		results.append(entry)
	var bdir := DirAccess.open(baselines)
	if bdir != null:
		for f: String in bdir.get_files():
			if not f.ends_with(".png"):
				continue
			if not base_prefix.is_empty() and not f.begins_with(base_prefix):
				continue
			var shot_name := f.trim_prefix(base_prefix).get_basename()
			if not seen.has(shot_name):
				results.append(
					{
						"shot": shot_name,
						"baseline": f,
						"status": "MISSING",
						"rmse": -1.0,
						"diff": ""
					}
				)
	_write(report, {"threshold": threshold, "prefix": prefix, "results": results})
	quit(0)


func _write_diff(a: Image, b: Image, path: String) -> void:
	var w := a.get_width()
	var h := a.get_height()
	var diff := Image.create_empty(w, h, false, Image.FORMAT_RGB8)
	for y in range(h):
		for x in range(w):
			var ca := a.get_pixel(x, y)
			var cb := b.get_pixel(x, y)
			var d := absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)
			if d > 0.05:
				diff.set_pixel(x, y, Color(1.0, 0.1, 0.1))
			else:
				diff.set_pixel(x, y, Color(ca.r * 0.3, ca.g * 0.3, ca.b * 0.3))
	diff.save_png(path)


func _write(path: String, data: Dictionary) -> void:
	if path.is_empty():
		print(JSON.stringify(data, "  "))
		return
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print(JSON.stringify(data, "  "))
		return
	f.store_string(JSON.stringify(data, "  "))
	f.close()
