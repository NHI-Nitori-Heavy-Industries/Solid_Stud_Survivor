"""Windows graphical interface for Solid Stud Survivor."""

import contextlib
import io
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from types import SimpleNamespace

import obj2stud

AUTHOR = "Aioli"
STUDIO_CUSTOM_PARTS = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "Stud.io",
    "CustomParts",
)

TEXT = {
    "將 OBJ 或 STL 模型轉換為 Stud.io 自訂零件": (
        "Convert OBJ or STL models into Stud.io custom parts"
    ),
    "OBJ / STL 模型檔案": "OBJ / STL model file",
    "模型檔案": "Model file",
    "選擇檔案...": "Browse...",
    "輸出根資料夾": "Output folder",
    "選擇資料夾...": "Browse...",
    "將自動輸出至 parts、collider、connectivity 子資料夾": (
        "Files will be placed in the parts, collider, and connectivity subfolders"
    ),
    "模型尺寸": "Model size",
    "設定成品寬度": "Set finished width",
    "寬度單位": "Width unit",
    "毫米 (mm)": "Millimeters (mm)",
    "Stud（7.8 mm）": "Studs (7.8 mm each)",
    "設定縮放倍率": "Set scale",
    "模型單位轉 mm，例如 0.0259": "Model units to mm, e.g. 0.0259",
    "選項": "Options",
    "零件名稱": "Part name",
    "作者": "Author",
    "小碎片下限": "Minimum piece size",
    "mm；0 代表不刪除": "mm; 0 disables removal",
    "減面目標": "Face target",
    "面；留空代表保留原面數": "faces; leave blank to keep all faces",
    "模型使用 Z 朝上座標": "Model uses Z-up coordinates",
    "模型物件（掃描後勾選要輸出的元件，預設全選）": (
        "Model objects (scan, then select objects to export; all selected by default)"
    ),
    "重新讀取物件": "Rescan objects",
    "全選": "Select all",
    "全不選": "Select none",
    "開始轉換": "Start conversion",
    "訊息": "Messages",
    "轉換完成": "Conversion complete",
    "轉換失敗": "Conversion failed",
    "物件掃描失敗。": "Object scan failed.",
    "物件掃描完成。": "Object scan complete.",
    "正在讀取模型物件...": "Reading model objects...",
    "正在讀取模型物件名稱與面數...": "Reading object names and face counts...",
    "模型中沒有可輸出的三角面。": "The model contains no exportable triangles.",
    "請先選擇模型檔案，程式會讀取物件名稱與面數。": (
        "Choose a model file to scan its object names and face counts."
    ),
    "請選擇 OBJ 或 STL 模型檔案。": "Select an OBJ or STL model file.",
    "轉換中，模型較大時可能需要一些時間...": (
        "Converting; large models may take some time..."
    ),
    "正在讀取模型物件...": "Reading model objects...",
    "正在讀取模型物件名稱與面數...": "Reading object names and face counts...",
    "物件掃描失敗。": "Object scan failed.",
    "物件掃描完成。": "Object scan complete.",
    "轉換完成。": "Conversion complete.",
    "轉換失敗。": "Conversion failed.",
    "請選擇 OBJ 或 STL 模型檔案。": "Select an OBJ or STL model file.",
    "模型讀取錯誤": "Model read error",
    "設定錯誤": "Invalid settings",
    "讀取失敗：{error}": "Read failed: {error}",
    "共 {count} 個物件，{faces:,} 面（初始全選）": (
        "{count} objects, {faces:,} faces (all selected by default)"
    ),
    "{name}  —  {faces:,} 面": "{name}  —  {faces:,} faces",
    "請先選擇 OBJ 或 STL 模型檔案。": "Select an OBJ or STL model file first.",
    "找不到指定的模型檔案。": "The selected model file could not be found.",
    "模型檔案必須是 .obj 或 .stl 格式。": "The model file must be an .obj or .stl file.",
    "請先讀取目前模型的物件清單，再選擇要輸出的元件。": (
        "Scan the current model and select objects to export first."
    ),
    "請至少勾選一個要輸出的物件。": "Select at least one object to export.",
    "請指定輸出根資料夾。": "Choose an output folder.",
    "小碎片下限必須是大於或等於 0 的數字。": (
        "Minimum piece size must be a number greater than or equal to 0."
    ),
    "請輸入有效且大於 0 的尺寸或縮放倍率。": (
        "Enter a valid width or scale greater than 0."
    ),
    "減面目標必須是正整數，或留空以保留原面數。": (
        "Face target must be a positive integer, or blank to keep all faces."
    ),
    "減面目標必須大於 0。": "Face target must be greater than 0.",
    "轉換中": "Converting",
    "轉換完成提示": "Stud.io custom-part files have been exported.",
}


class Obj2StudApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Solid Stud Survivor")
        self.root.minsize(720, 740)

        self.language = "zh"
        self.language_choice = tk.StringVar(value="繁體中文")
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=STUDIO_CUSTOM_PARTS)
        self.part_name = tk.StringVar()
        self.size_mode = tk.StringVar(value="width")
        self.width = tk.StringVar()
        self.width_unit = tk.StringVar(value="mm")
        self.width_unit_display = tk.StringVar(value="毫米 (mm)")
        self.scale = tk.StringVar()
        self.faces = tk.StringVar()
        self.min_piece = tk.StringVar(value="0")
        self.z_up = tk.BooleanVar(value=False)
        self.scanned_path = None
        self.object_vars = []
        self.object_data = []
        self.object_message = "請先選擇模型檔案，程式會讀取物件名稱與面數。"
        self.scan_generation = 0

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(6, weight=1)
        outer.rowconfigure(10, weight=1)

        title_bar = ttk.Frame(outer)
        title_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        title_bar.columnconfigure(0, weight=1)
        self.title_label = ttk.Label(
            title_bar,
            text="將 OBJ 或 STL 模型轉換為 Stud.io 自訂零件",
            font=("", 12, "bold"),
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        ttk.Label(title_bar, text="語言 / Language").grid(row=0, column=1, padx=(8, 4))
        self.language_selector = ttk.Combobox(
            title_bar,
            textvariable=self.language_choice,
            values=("繁體中文", "English"),
            state="readonly",
            width=12,
        )
        self.language_selector.grid(row=0, column=2, sticky="e")
        self.language_selector.bind("<<ComboboxSelected>>", self._change_language)

        ttk.Label(outer, text="模型檔案").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=self.input_path).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="選擇檔案...", command=self._choose_input).grid(
            row=1, column=2, padx=(8, 0), pady=4
        )

        ttk.Label(outer, text="輸出根資料夾").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(outer, textvariable=self.output_dir).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        ttk.Button(outer, text="選擇資料夾...", command=self._choose_output).grid(
            row=2, column=2, padx=(8, 0), pady=4
        )
        ttk.Label(
            outer,
            text="將自動輸出至 parts、collider、connectivity 子資料夾",
        ).grid(row=3, column=1, columnspan=2, sticky="w", pady=(0, 4))

        sizing = ttk.LabelFrame(outer, text="模型尺寸", padding=8)
        sizing.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 5))
        sizing.columnconfigure(3, weight=1)
        ttk.Radiobutton(
            sizing,
            text="設定成品寬度",
            variable=self.size_mode,
            value="width",
            command=self._update_size_controls,
        ).grid(row=0, column=0, sticky="w")
        self.width_entry = ttk.Entry(sizing, textvariable=self.width, width=12)
        self.width_entry.grid(row=0, column=1, sticky="w", padx=(8, 4))
        self.width_unit_selector = ttk.Combobox(
            sizing,
            textvariable=self.width_unit_display,
            state="readonly",
            width=20,
        )
        self.width_unit_selector.grid(row=0, column=2, sticky="w")
        self.width_unit_selector.bind(
            "<<ComboboxSelected>>", self._select_width_unit
        )

        ttk.Radiobutton(
            sizing,
            text="設定縮放倍率",
            variable=self.size_mode,
            value="scale",
            command=self._update_size_controls,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.scale_entry = ttk.Entry(sizing, textvariable=self.scale, width=12)
        self.scale_entry.grid(row=1, column=1, sticky="w", padx=(8, 4), pady=(6, 0))
        ttk.Label(sizing, text="模型單位轉 mm，例如 0.0259").grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(6, 0)
        )

        options = ttk.LabelFrame(outer, text="選項", padding=8)
        options.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=5)
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="零件名稱").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(options, textvariable=self.part_name).grid(
            row=0, column=1, sticky="ew", pady=3
        )
        ttk.Label(options, text="作者").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Label(options, text=AUTHOR).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(options, text="小碎片下限").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3
        )
        ttk.Entry(options, textvariable=self.min_piece, width=12).grid(
            row=2, column=1, sticky="w", pady=3
        )
        ttk.Label(options, text="mm；0 代表不刪除").grid(
            row=2, column=1, sticky="w", padx=(105, 0)
        )
        ttk.Label(options, text="減面目標").grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=3
        )
        ttk.Entry(options, textvariable=self.faces, width=12).grid(
            row=3, column=1, sticky="w", pady=3
        )
        ttk.Label(options, text="面；留空代表保留原面數").grid(
            row=3, column=1, sticky="w", padx=(105, 0)
        )
        ttk.Checkbutton(options, text="模型使用 Z 朝上座標", variable=self.z_up).grid(
            row=4, column=1, sticky="w", pady=(3, 0)
        )

        object_frame = ttk.LabelFrame(
            outer,
            text="模型物件（掃描後勾選要輸出的元件，預設全選）",
            padding=6,
        )
        object_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=5)
        object_frame.columnconfigure(0, weight=1)
        object_frame.rowconfigure(1, weight=1)
        object_actions = ttk.Frame(object_frame)
        object_actions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.scan_button = ttk.Button(
            object_actions, text="重新讀取物件", command=self._scan_objects
        )
        self.scan_button.pack(side="left")
        self.select_all_button = ttk.Button(
            object_actions, text="全選", command=lambda: self._select_objects(True)
        )
        self.select_all_button.pack(side="left", padx=(8, 0))
        self.select_none_button = ttk.Button(
            object_actions, text="全不選", command=lambda: self._select_objects(False)
        )
        self.select_none_button.pack(side="left", padx=(8, 0))

        self.object_canvas = tk.Canvas(object_frame, height=130, highlightthickness=0)
        self.object_canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            object_frame, orient="vertical", command=self.object_canvas.yview
        )
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.object_canvas.configure(yscrollcommand=scrollbar.set)
        self.object_list = ttk.Frame(self.object_canvas)
        self.object_window = self.object_canvas.create_window(
            (0, 0), window=self.object_list, anchor="nw"
        )
        self.object_list.bind("<Configure>", self._update_object_scrollregion)
        self.object_canvas.bind("<Configure>", self._resize_object_list)
        self._show_object_message(self.object_message)

        actions = ttk.Frame(outer)
        actions.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 6))
        self.convert_button = ttk.Button(
            actions, text="開始轉換", command=self._start_conversion
        )
        self.convert_button.pack(side="right")

        self.status = tk.StringVar(value="請選擇 OBJ 或 STL 模型檔案。")
        ttk.Label(outer, textvariable=self.status).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )

        log_frame = ttk.LabelFrame(outer, text="訊息", padding=6)
        log_frame.grid(row=10, column=0, columnspan=3, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=7, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=log_scrollbar.set)

        self._update_size_controls()
        self._apply_language()

    def _choose_input(self):
        path = filedialog.askopenfilename(
            title=self._tr("模型檔案"),
            filetypes=[
                (self._tr("OBJ / STL 模型檔案"), "*.obj *.stl"),
                ("OBJ", "*.obj"),
                ("STL", "*.stl"),
            ],
        )
        if path:
            self.input_path.set(path)
            self.part_name.set(os.path.splitext(os.path.basename(path))[0])
            self._scan_objects()

    def _choose_output(self):
        path = filedialog.askdirectory(
            title=self._tr("輸出根資料夾"),
            initialdir=self.output_dir.get() or STUDIO_CUSTOM_PARTS,
        )
        if path:
            self.output_dir.set(path)

    def _tr(self, text):
        if self.language == "en":
            return TEXT.get(text, text)
        english_to_chinese = {english: chinese for chinese, english in TEXT.items()}
        return english_to_chinese.get(text, text)

    def _change_language(self, _event=None):
        self.language = "en" if self.language_choice.get() == "English" else "zh"
        self._apply_language()

    def _apply_language(self):
        self.root.title("Solid Stud Survivor")
        self.title_label.configure(
            text=self._tr("將 OBJ 或 STL 模型轉換為 Stud.io 自訂零件")
        )
        for parent in (self.root,):
            self._translate_widgets(parent)
        self.width_unit_selector.configure(
            values=(
                self._tr("毫米 (mm)"),
                self._tr("Stud（7.8 mm）"),
            )
        )
        self.width_unit_display.set(
            self._tr("毫米 (mm)" if self.width_unit.get() == "mm" else "Stud（7.8 mm）")
        )
        self.status.set(self._tr(self.status.get()))
        self._render_objects()

    def _select_width_unit(self, _event=None):
        self.width_unit.set(
            "mm"
            if self.width_unit_display.get() == self._tr("毫米 (mm)")
            else "studs"
        )

    def _translate_widgets(self, parent):
        for child in parent.winfo_children():
            if child is self.title_label or child is self.language_selector:
                continue
            try:
                current_text = child.cget("text")
            except tk.TclError:
                current_text = None
            if current_text in TEXT:
                child.configure(text=self._tr(current_text))
            elif self.language == "zh":
                translated = self._tr(current_text)
                if translated != current_text:
                    child.configure(text=translated)
            self._translate_widgets(child)

    def _tr_format(self, template, **values):
        return self._tr(template).format(**values)

    def _update_size_controls(self):
        if self.size_mode.get() == "width":
            self.width_entry.state(["!disabled"])
            self.scale_entry.state(["disabled"])
        else:
            self.width_entry.state(["disabled"])
            self.scale_entry.state(["!disabled"])

    def _selected_input(self):
        path = self.input_path.get().strip()
        if not path:
            raise ValueError(self._tr("請先選擇 OBJ 或 STL 模型檔案。"))
        if not os.path.isfile(path):
            raise ValueError(self._tr("找不到指定的模型檔案。"))
        if os.path.splitext(path)[1].lower() not in (".obj", ".stl"):
            raise ValueError(self._tr("模型檔案必須是 .obj 或 .stl 格式。"))
        return path

    def _set_log(self, text, clear=False):
        self.log.configure(state="normal")
        if clear:
            self.log.delete("1.0", "end")
        if text:
            self.log.insert("end", text)
            if not text.endswith("\n"):
                self.log.insert("end", "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _show_object_message(self, text):
        self.object_message = text
        self.object_data.clear()
        self.object_vars.clear()
        self._render_objects()

    def _render_objects(self):
        if not hasattr(self, "object_list"):
            return
        for child in self.object_list.winfo_children():
            child.destroy()
        if self.object_data:
            for row, (name, face_count, selected) in enumerate(self.object_data):
                ttk.Checkbutton(
                    self.object_list,
                    text=self._tr_format("{name}  —  {faces:,} 面", name=name, faces=face_count),
                    variable=selected,
                ).grid(row=row, column=0, sticky="w", padx=4, pady=1)
            total_faces = sum(face_count for _, face_count, _ in self.object_data)
            ttk.Label(
                self.object_list,
                text=self._tr_format(
                    "共 {count} 個物件，{faces:,} 面（初始全選）",
                    count=len(self.object_data),
                    faces=total_faces,
                ),
            ).grid(row=len(self.object_data), column=0, sticky="w", padx=4, pady=(5, 4))
        else:
            ttk.Label(
                self.object_list, text=self._tr(self.object_message)
            ).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.object_canvas.configure(scrollregion=self.object_canvas.bbox("all"))

    def _update_object_scrollregion(self, _event=None):
        self.object_canvas.configure(scrollregion=self.object_canvas.bbox("all"))

    def _resize_object_list(self, event):
        self.object_canvas.itemconfigure(self.object_window, width=event.width)

    def _set_busy(self, busy, status):
        state = "disabled" if busy else "normal"
        self.convert_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.select_all_button.configure(state=state)
        self.select_none_button.configure(state=state)
        self.status.set(self._tr(status))

    def _scan_objects(self):
        try:
            path = self._selected_input()
        except ValueError as exc:
            messagebox.showerror(self._tr("模型讀取錯誤"), str(exc), parent=self.root)
            return
        self.scan_generation += 1
        generation = self.scan_generation
        self.scanned_path = None
        self._show_object_message("正在讀取模型物件...")
        self._set_busy(True, "正在讀取模型物件名稱與面數...")
        threading.Thread(
            target=self._scan_worker, args=(path, generation), daemon=True
        ).start()

    def _scan_worker(self, path, generation):
        try:
            extension = os.path.splitext(path)[1].lower()
            _vertices, groups = (
                obj2stud.read_stl(path) if extension == ".stl" else obj2stud.read_obj(path)
            )
            self.root.after(
                0, self._finish_scan, path, generation, groups, None
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self.root.after(0, self._finish_scan, path, generation, None, str(exc))

    def _finish_scan(self, path, generation, groups, error):
        if generation != self.scan_generation:
            return
        self._set_busy(False, "物件掃描失敗。" if error else "物件掃描完成。")
        if error is not None:
            self.scanned_path = None
            self._show_object_message(self._tr_format("讀取失敗：{error}", error=error))
            messagebox.showerror(self._tr("模型讀取錯誤"), error, parent=self.root)
            return
        if not groups:
            self.scanned_path = None
            self._show_object_message("模型中沒有可輸出的三角面。")
            return

        self.scanned_path = os.path.normcase(os.path.abspath(path))
        self.object_vars.clear()
        self.object_data.clear()
        for name, faces in groups:
            selected = tk.BooleanVar(value=True)
            self.object_vars.append((name, selected))
            self.object_data.append((name, len(faces), selected))
        self._render_objects()

    def _select_objects(self, selected):
        for _, variable in self.object_vars:
            variable.set(selected)

    def _make_arguments(self):
        input_path = self._selected_input()
        normalized_path = os.path.normcase(os.path.abspath(input_path))
        if self.scanned_path != normalized_path:
            raise ValueError(
                self._tr("請先讀取目前模型的物件清單，再選擇要輸出的元件。")
            )
        included_objects = [name for name, variable in self.object_vars if variable.get()]
        if not included_objects:
            raise ValueError(self._tr("請至少勾選一個要輸出的物件。"))

        output_value = os.path.expandvars(self.output_dir.get().strip())
        if not output_value:
            raise ValueError(self._tr("請指定輸出根資料夾。"))
        output_root = os.path.abspath(output_value)
        parts_dir = os.path.join(output_root, "parts")
        collider_dir = os.path.join(output_root, "collider")
        connectivity_dir = os.path.join(output_root, "connectivity")

        try:
            min_piece = obj2stud.valid_nonnegative_float(self.min_piece.get().strip())
        except (ValueError, TypeError) as exc:
            raise ValueError(self._tr("小碎片下限必須是大於或等於 0 的數字。")) from exc

        width = None
        scale = None
        try:
            if self.size_mode.get() == "width":
                width_value = obj2stud.valid_positive_float(self.width.get().strip())
                width = (
                    obj2stud.studs_to_mm(width_value)
                    if self.width_unit.get() == "studs"
                    else width_value
                )
            else:
                scale = obj2stud.valid_positive_float(self.scale.get().strip())
        except (ValueError, TypeError) as exc:
            raise ValueError(self._tr("請輸入有效且大於 0 的尺寸或縮放倍率。")) from exc

        faces_text = self.faces.get().strip()
        try:
            target_faces = int(faces_text) if faces_text else None
        except ValueError as exc:
            raise ValueError(
                self._tr("減面目標必須是正整數，或留空以保留原面數。")
            ) from exc
        if target_faces is not None and target_faces <= 0:
            raise ValueError(self._tr("減面目標必須大於 0。"))

        name = self.part_name.get().strip() or os.path.splitext(os.path.basename(input_path))[0]
        obj2stud.validate_part_name(name)
        return SimpleNamespace(
            input=input_path,
            width=width,
            scale=scale,
            name=name,
            out=output_root,
            parts_dir=parts_dir,
            collider_dir=collider_dir,
            connectivity_dir=connectivity_dir,
            faces=target_faces,
            min_piece=min_piece,
            drop=[],
            include_objects=included_objects,
            zup=self.z_up.get(),
            author=AUTHOR,
            weld_tol=1e-5,
            list=False,
        )

    def _start_conversion(self):
        try:
            arguments = self._make_arguments()
        except ValueError as exc:
            messagebox.showerror(self._tr("設定錯誤"), str(exc), parent=self.root)
            return

        self._set_busy(True, "轉換中，模型較大時可能需要一些時間...")
        self._set_log("", clear=True)
        threading.Thread(
            target=self._conversion_worker, args=(arguments,), daemon=True
        ).start()

    def _conversion_worker(self, arguments):
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                obj2stud.run(arguments)
            self.root.after(0, self._finish_conversion, output.getvalue(), None)
        except (OSError, RuntimeError, ValueError) as exc:
            self.root.after(0, self._finish_conversion, output.getvalue(), str(exc))

    def _finish_conversion(self, output, error):
        self._set_busy(False, "轉換完成。" if error is None else "轉換失敗。")
        self._set_log(output if error is None else f"{output}錯誤：{error}", clear=True)
        if error is None:
            messagebox.showinfo(
                self._tr("轉換完成"),
                self._tr("轉換完成提示"),
                parent=self.root,
            )
        else:
            messagebox.showerror(self._tr("轉換失敗"), error, parent=self.root)


def main():
    root = tk.Tk()
    Obj2StudApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
