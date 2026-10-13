"""Windows graphical interface for the obj2stud converter."""

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


class Obj2StudApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OBJ / STL 轉 Stud.io 自訂零件")
        self.root.minsize(720, 740)

        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=STUDIO_CUSTOM_PARTS)
        self.part_name = tk.StringVar()
        self.size_mode = tk.StringVar(value="width")
        self.width = tk.StringVar()
        self.scale = tk.StringVar()
        self.faces = tk.StringVar()
        self.min_piece = tk.StringVar(value="2")
        self.z_up = tk.BooleanVar(value=False)
        self.scanned_path = None
        self.object_vars = []
        self.scan_generation = 0

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(6, weight=1)
        outer.rowconfigure(10, weight=1)

        ttk.Label(
            outer,
            text="將 OBJ 或 STL 模型轉換為 Stud.io 自訂零件",
            font=("", 12, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

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
        sizing.columnconfigure(2, weight=1)
        ttk.Radiobutton(
            sizing,
            text="設定成品寬度",
            variable=self.size_mode,
            value="width",
            command=self._update_size_controls,
        ).grid(row=0, column=0, sticky="w")
        self.width_entry = ttk.Entry(sizing, textvariable=self.width, width=12)
        self.width_entry.grid(row=0, column=1, sticky="w", padx=(8, 4))
        ttk.Label(sizing, text="mm").grid(row=0, column=2, sticky="w")

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
            row=1, column=2, sticky="w", pady=(6, 0)
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
        self._show_object_message("請先選擇模型檔案，程式會讀取物件名稱與面數。")

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

    def _choose_input(self):
        path = filedialog.askopenfilename(
            title="選擇模型檔案",
            filetypes=[("3D 模型", "*.obj *.stl"), ("OBJ 模型", "*.obj"), ("STL 模型", "*.stl")],
        )
        if path:
            self.input_path.set(path)
            self.part_name.set(os.path.splitext(os.path.basename(path))[0])
            self._scan_objects()

    def _choose_output(self):
        path = filedialog.askdirectory(
            title="選擇輸出根資料夾",
            initialdir=self.output_dir.get() or STUDIO_CUSTOM_PARTS,
        )
        if path:
            self.output_dir.set(path)

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
            raise ValueError("請先選擇 OBJ 或 STL 模型檔案。")
        if not os.path.isfile(path):
            raise ValueError("找不到指定的模型檔案。")
        if os.path.splitext(path)[1].lower() not in (".obj", ".stl"):
            raise ValueError("模型檔案必須是 .obj 或 .stl 格式。")
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
        for child in self.object_list.winfo_children():
            child.destroy()
        self.object_vars.clear()
        ttk.Label(self.object_list, text=text).grid(row=0, column=0, sticky="w", padx=4, pady=4)
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
        self.status.set(status)

    def _scan_objects(self):
        try:
            path = self._selected_input()
        except ValueError as exc:
            messagebox.showerror("無法讀取模型", str(exc), parent=self.root)
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
            self._show_object_message(f"讀取失敗：{error}")
            messagebox.showerror("無法讀取模型", error, parent=self.root)
            return
        if not groups:
            self.scanned_path = None
            self._show_object_message("模型中沒有可輸出的三角面。")
            return

        self.scanned_path = os.path.normcase(os.path.abspath(path))
        for child in self.object_list.winfo_children():
            child.destroy()
        self.object_vars.clear()
        for row, (name, faces) in enumerate(groups):
            selected = tk.BooleanVar(value=True)
            self.object_vars.append((name, selected))
            ttk.Checkbutton(
                self.object_list,
                text=f"{name}  —  {len(faces):,} 面",
                variable=selected,
            ).grid(row=row, column=0, sticky="w", padx=4, pady=1)
        total_faces = sum(len(faces) for _, faces in groups)
        ttk.Label(
            self.object_list,
            text=f"共 {len(groups)} 個物件，{total_faces:,} 面（初始全選）",
        ).grid(row=len(groups), column=0, sticky="w", padx=4, pady=(5, 4))
        self.object_canvas.configure(scrollregion=self.object_canvas.bbox("all"))

    def _select_objects(self, selected):
        for _, variable in self.object_vars:
            variable.set(selected)

    def _make_arguments(self):
        input_path = self._selected_input()
        normalized_path = os.path.normcase(os.path.abspath(input_path))
        if self.scanned_path != normalized_path:
            raise ValueError("請先讀取目前模型的物件清單，再選擇要輸出的元件。")
        included_objects = [name for name, variable in self.object_vars if variable.get()]
        if not included_objects:
            raise ValueError("請至少勾選一個要輸出的物件。")

        output_value = os.path.expandvars(self.output_dir.get().strip())
        if not output_value:
            raise ValueError("請指定輸出根資料夾。")
        output_root = os.path.abspath(output_value)
        parts_dir = os.path.join(output_root, "parts")
        collider_dir = os.path.join(output_root, "collider")
        connectivity_dir = os.path.join(output_root, "connectivity")

        try:
            min_piece = obj2stud.valid_nonnegative_float(self.min_piece.get().strip())
        except (ValueError, TypeError) as exc:
            raise ValueError("小碎片下限必須是大於或等於 0 的數字。") from exc

        width = None
        scale = None
        try:
            if self.size_mode.get() == "width":
                width = obj2stud.valid_positive_float(self.width.get().strip())
            else:
                scale = obj2stud.valid_positive_float(self.scale.get().strip())
        except (ValueError, TypeError) as exc:
            raise ValueError("請輸入有效且大於 0 的尺寸或縮放倍率。") from exc

        faces_text = self.faces.get().strip()
        try:
            target_faces = int(faces_text) if faces_text else None
        except ValueError as exc:
            raise ValueError("減面目標必須是正整數，或留空以保留原面數。") from exc
        if target_faces is not None and target_faces <= 0:
            raise ValueError("減面目標必須大於 0。")

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
            messagebox.showerror("設定有誤", str(exc), parent=self.root)
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
            messagebox.showinfo("轉換完成", "Stud.io 自訂零件檔案已輸出。", parent=self.root)
        else:
            messagebox.showerror("轉換失敗", error, parent=self.root)


def main():
    root = tk.Tk()
    Obj2StudApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
