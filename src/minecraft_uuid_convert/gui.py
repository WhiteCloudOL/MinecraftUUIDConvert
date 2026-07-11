"""Tkinter desktop interface for Minecraft UUID Convert."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from minecraft_uuid_convert.cache import CacheFormatError, load_player_cache
from minecraft_uuid_convert.converter import (
    ConversionError,
    ConversionMode,
    ConversionOptions,
    ConversionResult,
    convert_directory,
)

COLORS = {
    "slate": "#18252C",
    "slate_2": "#22333B",
    "stone": "#F3F1EA",
    "paper": "#FCFBF7",
    "ink": "#203039",
    "muted": "#66757B",
    "grass": "#5E7E55",
    "grass_dark": "#486542",
    "water": "#4E8197",
    "copper": "#C6784A",
    "line": "#D8D7D0",
    "white": "#FFFFFF",
}


class UUIDConvertApp:
    """Non-blocking desktop workflow for directory conversion."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Minecraft UUID Convert")
        self.root.geometry("980x720")
        self.root.minsize(900, 650)
        self.root.configure(bg=COLORS["stone"])
        self._icon_image: tk.PhotoImage | None = None
        self._load_window_icon()
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()

        base = Path.cwd()
        self.input_var = tk.StringVar(value=str(base / "input"))
        self.output_var = tk.StringVar(value=str(base / "output"))
        self.cache_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=ConversionMode.ONLINE_TO_OFFLINE.value)
        self.network_var = tk.BooleanVar(value=True)
        self.text_var = tk.BooleanVar(value=True)
        self.recursive_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="等待开始")

        self._configure_styles()
        self._build_layout()
        self._mode_changed()
        self.root.after(100, self._poll_events)

    def _load_window_icon(self) -> None:
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        try:
            self._icon_image = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self._icon_image)
        except (OSError, tk.TclError):
            self._icon_image = None

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(
            "TEntry",
            fieldbackground=COLORS["white"],
            foreground=COLORS["ink"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            padding=9,
        )
        style.map("TEntry", bordercolor=[("focus", COLORS["water"])])
        style.configure(
            "Browse.TButton",
            background=COLORS["paper"],
            foreground=COLORS["ink"],
            bordercolor=COLORS["line"],
            padding=(12, 8),
            font=("Microsoft YaHei UI", 9),
        )
        style.map(
            "Browse.TButton",
            background=[("active", COLORS["stone"]), ("pressed", COLORS["line"])],
        )
        style.configure(
            "Primary.TButton",
            background=COLORS["grass"],
            foreground=COLORS["white"],
            bordercolor=COLORS["grass"],
            padding=(20, 11),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", COLORS["grass_dark"]),
                ("pressed", COLORS["grass_dark"]),
                ("disabled", "#9BAA97"),
            ],
        )
        style.configure(
            "TRadiobutton",
            background=COLORS["paper"],
            foreground=COLORS["ink"],
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "TCheckbutton",
            background=COLORS["paper"],
            foreground=COLORS["ink"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Pipeline.Horizontal.TProgressbar",
            background=COLORS["water"],
            troughcolor="#DCE5E6",
            bordercolor=COLORS["paper"],
            lightcolor=COLORS["water"],
            darkcolor=COLORS["water"],
            thickness=8,
        )

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["stone"])
        shell.pack(fill="both", expand=True, padx=18, pady=18)

        sidebar = tk.Frame(shell, bg=COLORS["slate"], width=252)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        main = tk.Frame(shell, bg=COLORS["paper"])
        main.pack(side="left", fill="both", expand=True)
        self._build_main(main)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        brand = tk.Label(
            parent,
            text="WORLD\nIDENTITY",
            justify="left",
            bg=COLORS["slate"],
            fg=COLORS["white"],
            font=("Segoe UI Semibold", 22),
        )
        brand.pack(anchor="w", padx=28, pady=(32, 4))
        tk.Label(
            parent,
            text="Minecraft Java UUID 迁移工作台",
            bg=COLORS["slate"],
            fg="#AFC0C6",
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=28)

        canvas = tk.Canvas(
            parent,
            width=196,
            height=76,
            bg=COLORS["slate"],
            highlightthickness=0,
        )
        canvas.pack(padx=28, pady=(34, 28))
        cells = [
            COLORS["grass"],
            COLORS["grass"],
            COLORS["water"],
            COLORS["water"],
            "#70838A",
            COLORS["copper"],
            COLORS["copper"],
            "#70838A",
            COLORS["slate_2"],
            "#70838A",
            COLORS["grass"],
            COLORS["slate_2"],
        ]
        for index, color in enumerate(cells):
            x = (index % 4) * 49
            y = (index // 4) * 25
            canvas.create_rectangle(x + 2, y + 2, x + 45, y + 22, fill=color, width=0)

        steps = [
            ("01", "识别", "筛选目标 UUID 版本"),
            ("02", "解析", "缓存与官方服务校验"),
            ("03", "镜像", "保留目录与未转换文件"),
        ]
        for number, title, detail in steps:
            row = tk.Frame(parent, bg=COLORS["slate"])
            row.pack(fill="x", padx=28, pady=9)
            tk.Label(
                row,
                text=number,
                bg=COLORS["slate"],
                fg=COLORS["copper"],
                font=("Cascadia Mono", 9, "bold"),
            ).pack(side="left", anchor="n", padx=(0, 12))
            copy = tk.Frame(row, bg=COLORS["slate"])
            copy.pack(side="left", fill="x")
            tk.Label(
                copy,
                text=title,
                bg=COLORS["slate"],
                fg=COLORS["white"],
                font=("Microsoft YaHei UI", 10, "bold"),
            ).pack(anchor="w")
            tk.Label(
                copy,
                text=detail,
                bg=COLORS["slate"],
                fg="#91A4AA",
                font=("Microsoft YaHei UI", 8),
            ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            parent,
            text="SOURCE SAFE  ·  OUTPUT MIRROR",
            bg=COLORS["slate"],
            fg="#738990",
            font=("Cascadia Mono", 8),
        ).pack(side="bottom", anchor="w", padx=28, pady=26)

    def _build_main(self, parent: tk.Frame) -> None:
        canvas = tk.Canvas(
            parent,
            bg=COLORS["paper"],
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(canvas, bg=COLORS["paper"])
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(-event.delta // 120, "units"),
        )
        content.configure(padx=36, pady=30)
        content.columnconfigure(0, weight=1)

        tk.Label(
            content,
            text="迁移玩家身份",
            bg=COLORS["paper"],
            fg=COLORS["ink"],
            font=("Microsoft YaHei UI", 22, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            content,
            text="选择世界根目录或 playerdata / stats / advancements 等数据目录。",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).grid(row=1, column=0, sticky="w", pady=(4, 22))

        form = tk.Frame(content, bg=COLORS["paper"])
        form.grid(row=2, column=0, sticky="nsew")
        form.columnconfigure(0, weight=1)

        self._path_row(
            form,
            row=0,
            label="世界或数据目录",
            variable=self.input_var,
            command=lambda: self._choose_directory(self.input_var),
        )

        tk.Label(
            form,
            text="转换方向",
            bg=COLORS["paper"],
            fg=COLORS["ink"],
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(17, 7))
        modes = tk.Frame(form, bg=COLORS["paper"])
        modes.grid(row=3, column=0, sticky="w")
        for mode in ConversionMode:
            ttk.Radiobutton(
                modes,
                text=mode.label,
                variable=self.mode_var,
                value=mode.value,
                command=self._mode_changed,
            ).pack(side="left", padx=(0, 24))

        self._path_row(
            form,
            row=4,
            label="玩家缓存（可选，离线转正版时建议提供）",
            variable=self.cache_var,
            command=self._choose_cache,
        )
        self.cache_hint = tk.Label(
            form,
            text="",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 8),
        )
        self.cache_hint.grid(row=6, column=0, sticky="w", pady=(5, 0))

        self._path_row(
            form,
            row=7,
            label="输出目录",
            variable=self.output_var,
            command=lambda: self._choose_directory(self.output_var),
        )

        options = tk.Frame(form, bg=COLORS["paper"])
        options.grid(row=9, column=0, sticky="w", pady=(17, 0))
        ttk.Checkbutton(
            options,
            text="递归处理子目录",
            variable=self.recursive_var,
        ).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(
            options,
            text="替换文本 UUID 引用",
            variable=self.text_var,
        ).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(
            options,
            text="允许在线玩家查询",
            variable=self.network_var,
        ).pack(side="left")

        separator = tk.Frame(form, height=1, bg=COLORS["line"])
        separator.grid(row=10, column=0, sticky="ew", pady=22)

        status_header = tk.Frame(form, bg=COLORS["paper"])
        status_header.grid(row=11, column=0, sticky="ew")
        status_header.columnconfigure(0, weight=1)
        tk.Label(
            status_header,
            textvariable=self.status_var,
            bg=COLORS["paper"],
            fg=COLORS["ink"],
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            status_header,
            text="日志固定保存到 ./logs/",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Cascadia Mono", 8),
        ).grid(row=0, column=1, sticky="e")

        self.progressbar = ttk.Progressbar(
            form,
            style="Pipeline.Horizontal.TProgressbar",
            mode="indeterminate",
        )
        self.progressbar.grid(row=12, column=0, sticky="ew", pady=(9, 10))

        self.log_text = tk.Text(
            form,
            height=5,
            bg="#EEF0EC",
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief="flat",
            padx=12,
            pady=10,
            font=("Cascadia Mono", 8),
            state="disabled",
            wrap="word",
        )
        self.log_text.grid(row=13, column=0, sticky="nsew")

        actions = tk.Frame(form, bg=COLORS["paper"])
        actions.grid(row=14, column=0, sticky="ew", pady=(16, 0))
        self.open_button = ttk.Button(
            actions,
            text="打开输出",
            style="Browse.TButton",
            command=self._open_output,
        )
        self.open_button.pack(side="left")
        self.start_button = ttk.Button(
            actions,
            text="开始镜像并转换",
            style="Primary.TButton",
            command=self._start_conversion,
        )
        self.start_button.pack(side="right")

    def _path_row(
        self,
        parent: tk.Frame,
        *,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: object,
    ) -> None:
        tk.Label(
            parent,
            text=label,
            bg=COLORS["paper"],
            fg=COLORS["ink"],
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 17, 7))
        row_frame = tk.Frame(parent, bg=COLORS["paper"])
        row_frame.grid(row=row + 1, column=0, sticky="ew")
        row_frame.columnconfigure(0, weight=1)
        ttk.Entry(row_frame, textvariable=variable).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            row_frame,
            text="浏览…",
            style="Browse.TButton",
            command=command,
        ).grid(row=0, column=1, padx=(8, 0))

    def _choose_directory(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(initialdir=variable.get() or str(Path.cwd()))
        if selected:
            variable.set(selected)

    def _choose_cache(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 usercache 或 usernamecache",
            filetypes=[("JSON 玩家缓存", "*.json"), ("所有文件", "*.*")],
        )
        if selected:
            self.cache_var.set(selected)

    def _mode_changed(self) -> None:
        if self.mode_var.get() == ConversionMode.ONLINE_TO_OFFLINE.value:
            text = "缓存可减少网络查询；没有缓存时会按正版 UUID 在线反查玩家名。"
        else:
            text = "离线 UUID 无法反推出玩家名，请提供包含对应玩家名的一份缓存。"
        self.cache_hint.configure(text=text)

    def _start_conversion(self) -> None:
        try:
            input_dir = Path(self.input_var.get().strip() or Path.cwd() / "input")
            output_dir = Path(self.output_var.get().strip() or Path.cwd() / "output")
            cache_path = self.cache_var.get().strip()
            cache = load_player_cache(Path(cache_path)) if cache_path else None
        except CacheFormatError as exc:
            messagebox.showerror("缓存无法使用", str(exc), parent=self.root)
            return

        options = ConversionOptions(
            input_dir=input_dir,
            output_dir=output_dir,
            logs_dir=Path.cwd() / "logs",
            mode=ConversionMode(self.mode_var.get()),
            cache=cache,
            use_network=self.network_var.get(),
            replace_text_references=self.text_var.get(),
            recursive=self.recursive_var.get(),
        )
        self.start_button.configure(state="disabled")
        self.status_var.set("正在处理")
        self._clear_log()
        self.progressbar.start(12)

        thread = threading.Thread(
            target=self._conversion_worker,
            args=(options,),
            daemon=True,
        )
        thread.start()

    def _conversion_worker(self, options: ConversionOptions) -> None:
        try:
            result = convert_directory(
                options,
                progress=lambda message: self._events.put(("progress", message)),
            )
        except (ConversionError, OSError, ValueError) as exc:
            self._events.put(("error", str(exc)))
        else:
            self._events.put(("done", result))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self._events.get_nowait()
                if event == "progress":
                    self._append_log(str(payload))
                elif event == "error":
                    self._finish_with_error(str(payload))
                elif event == "done" and isinstance(payload, ConversionResult):
                    self._finish_success(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _finish_success(self, result: ConversionResult) -> None:
        self.progressbar.stop()
        self.start_button.configure(state="normal")
        self.status_var.set("转换完成")
        summary = (
            f"已完整复制 {result.copied_files}/{result.total_files} 个文件；"
            f"改名 {result.renamed_files} 个，"
            f"更新文本 {result.modified_text_files} 个；"
            f"未解析 UUID {len(result.unresolved)} 个，"
            f"冲突 {len(result.collisions)} 个。"
        )
        self._append_log(summary)
        if result.log_file:
            self._append_log(f"详细日志：{result.log_file}")
        messagebox.showinfo("转换完成", summary, parent=self.root)

    def _finish_with_error(self, message: str) -> None:
        self.progressbar.stop()
        self.start_button.configure(state="normal")
        self.status_var.set("未完成")
        self._append_log(message)
        messagebox.showerror("无法完成转换", message, parent=self.root)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _open_output(self) -> None:
        output = Path(self.output_var.get().strip() or Path.cwd() / "output")
        output.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(output)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("无法打开输出目录", str(exc), parent=self.root)


def run_gui() -> None:
    """Create and run the desktop application."""
    root = tk.Tk()
    UUIDConvertApp(root)
    root.mainloop()
