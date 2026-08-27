#!/usr/bin/env python3
"""
WebP/GIF Converter
带图形界面，支持双击运行和拖拽文件/文件夹
支持 WebP 和 GIF 格式的转换与帧提取

功能：
- 拖入文件或文件夹进入等待区，或点击「选择文件 / 选择文件夹」加入等待区
- 点击「开始转换」统一处理等待区内的所有内容
- 可指定输出路径，优先级：指定路径 > 原文件所在路径 > 桌面
"""

import sys
import threading
import ctypes
from pathlib import Path
from PIL import Image

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk

# 拖放支持：tkinterdnd2 是最可靠的 Tk 拖放库
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _TKDND_AVAILABLE = True
except Exception:
    _TKDND_AVAILABLE = False

MAX_SIZE = 1024
VERSION = "V2.1.0"


def resize_if_needed(img: Image.Image) -> tuple[Image.Image, str | None]:
    """若宽或高超过 MAX_SIZE，则等比例缩小至 MAX_SIZE 以内"""
    width, height = img.size
    if width <= MAX_SIZE and height <= MAX_SIZE:
        return img, None

    scale = min(MAX_SIZE / width, MAX_SIZE / height)
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))
    scale_percent = scale * 100
    message = (
        f"  尺寸已调整: {width}x{height} -> {new_width}x{new_height}，"
        f"缩小至原尺寸的 {scale_percent:.1f}%"
    )
    return img.resize((new_width, new_height), Image.LANCZOS), message


def _prepare_gif_frame(
    frame: Image.Image, bg_color: tuple[int, int, int] | None = None
) -> tuple[Image.Image, int | None]:
    """将 RGBA 帧转换为 GIF 可用的调色板模式，并保留完全透明像素。

    问题背景：直接 ``convert('RGBA').convert('P', palette=ADAPTIVE)`` 会丢掉 alpha，
    导致原本透明的区域被填充成黑色或白色，转换后的 GIF 出现黑边/白边。

    这里采用的处理方式：
    - 完全不透明的帧：正常量化为 256 色调色板。
    - 带透明的帧：预留一个调色板索引给透明色，alpha < 128 的像素标记为透明。
    - 如果传入 ``bg_color``，则先把半透明像素合成到该背景色上（适合需要固定背景时）。

    返回 (palette_image, transparent_index)，没有透明区域时 transparent_index 为 None。
    """
    if frame.mode != "RGBA":
        frame = frame.convert("RGBA")

    alpha = frame.getchannel("A")
    min_a, max_a = alpha.getextrema()
    if min_a == 255:
        # 没有透明像素，直接量化
        return frame.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=256), None

    # 处理半透明/透明像素
    if bg_color is not None:
        bg = Image.new("RGBA", frame.size, (*bg_color, 255))
        rgb = Image.alpha_composite(bg, frame).convert("RGB")
    else:
        # 不额外加背景，直接丢弃 alpha，后面把透明像素统一标为透明索引
        rgb = frame.convert("RGB")

    # 预留索引 255 给透明色
    quantized = rgb.convert("P", palette=Image.ADAPTIVE, colors=255)
    transparent_index = 255
    transparent_mask = alpha.point(lambda a: 255 if a < 128 else 0, mode="1")

    if transparent_mask.getbbox() is not None:
        transparent_fill = Image.new("P", frame.size, transparent_index)
        quantized.paste(transparent_fill, (0, 0), transparent_mask)

        palette = quantized.getpalette()
        if palette is None:
            palette = []
        # 补齐到 256 色调色板长度
        if len(palette) < 768:
            palette.extend([0] * (768 - len(palette)))
        palette[transparent_index * 3 : transparent_index * 3 + 3] = (
            list(bg_color) if bg_color is not None else [255, 255, 255]
        )
        quantized.putpalette(palette)
        quantized.info["transparency"] = transparent_index

    return quantized, transparent_index


def convert_webp_to_gif(input_path: str, output_path: str) -> str | None:
    """将单个 WebP 文件转换为 GIF，若发生缩放则返回说明文字"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    resize_note = None

    with Image.open(input_path) as img:
        is_animated = getattr(img, "is_animated", False)
        n_frames = getattr(img, "n_frames", 1)

        if is_animated and n_frames > 1:
            frames = []
            durations = []
            transparency_used = False

            for frame_idx in range(n_frames):
                img.seek(frame_idx)
                frame, note = resize_if_needed(img.convert("RGBA"))
                if note:
                    resize_note = note
                frame, t_idx = _prepare_gif_frame(frame)
                if t_idx is not None:
                    transparency_used = True
                frames.append(frame)
                duration = img.info.get("duration", 100)
                durations.append(duration)

            save_kwargs = {
                "save_all": True,
                "append_images": frames[1:],
                "duration": durations,
                "loop": img.info.get("loop", 0),
                "optimize": True,
            }
            if transparency_used:
                # 透明帧需要 disposal=2，否则下一帧会透过透明区域显示上一帧
                save_kwargs["disposal"] = 2

            frames[0].save(output_file, **save_kwargs)
        else:
            t_idx = None
            if img.mode in ("RGBA", "P"):
                rgba, note = resize_if_needed(img.convert("RGBA"))
                if note:
                    resize_note = note
                img, t_idx = _prepare_gif_frame(rgba)
            elif img.mode != "P":
                img, resize_note = resize_if_needed(img.convert("RGB"))
                img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
            else:
                img, resize_note = resize_if_needed(img)
                img = img.convert("P", palette=Image.ADAPTIVE, colors=256)

            save_kwargs = {"optimize": True}
            img.save(output_file, "GIF", **save_kwargs)

    return resize_note


def convert_webp_to_png(input_path: str, output_path: str) -> str | None:
    """将单个 WebP 文件转换为 PNG，若发生缩放则保存两个版本（原始大小和缩小版）并返回说明文字"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    resize_note = None

    with Image.open(input_path) as img:
        is_animated = getattr(img, "is_animated", False)
        n_frames = getattr(img, "n_frames", 1)

        if is_animated and n_frames > 1:
            # 动图只取第一帧转为 PNG
            img.seek(0)
            original_frame = img.convert("RGBA")
            resized_frame, note = resize_if_needed(original_frame)
            if note:
                resize_note = note
                # 保存原始大小版本
                original_frame.save(output_file, "PNG")
                # 保存缩小版本
                resized_file = output_file.parent / f"{output_file.stem}_resized{output_file.suffix}"
                resized_frame.save(resized_file, "PNG")
                resize_note = f"  已保存两个版本：原始大小 ({original_frame.size[0]}x{original_frame.size[1]}) 和缩小版 ({resized_frame.size[0]}x{resized_frame.size[1]})"
            else:
                # 不需要缩小，只保存一个版本
                original_frame.save(output_file, "PNG")
        else:
            if img.mode in ("RGBA", "P"):
                original_img = img.convert("RGBA")
            else:
                original_img = img.convert("RGB")
            
            resized_img, note = resize_if_needed(original_img)
            if note:
                resize_note = note
                # 保存原始大小版本
                original_img.save(output_file, "PNG")
                # 保存缩小版本
                resized_file = output_file.parent / f"{output_file.stem}_resized{output_file.suffix}"
                resized_img.save(resized_file, "PNG")
                resize_note = f"  已保存两个版本：原始大小 ({original_img.size[0]}x{original_img.size[1]}) 和缩小版 ({resized_img.size[0]}x{resized_img.size[1]})"
            else:
                # 不需要缩小，只保存一个版本
                original_img.save(output_file, "PNG")

    return resize_note


def extract_frames(input_path: str, output_dir: str) -> tuple[int, str | None]:
    """将动图（WebP 或 GIF）的每一帧提取为单独的 PNG 文件，返回 (帧数, 缩放说明)
    若发生缩放，同时保存原始大小和缩小两个版本"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resize_note = None
    stem = Path(input_path).stem
    resized_saved = False

    with Image.open(input_path) as img:
        is_animated = getattr(img, "is_animated", False)
        n_frames = getattr(img, "n_frames", 1)

        if not is_animated or n_frames <= 1:
            # 静态图直接保存一帧
            original_frame = img.convert("RGBA")
            resized_frame, note = resize_if_needed(original_frame)
            if note:
                resize_note = note
                # 保存原始大小版本
                original_frame.save(out_dir / f"{stem}_001.png", "PNG")
                # 保存缩小版本
                resized_frame.save(out_dir / f"{stem}_001_resized.png", "PNG")
                resized_saved = True
            else:
                original_frame.save(out_dir / f"{stem}_001.png", "PNG")
            if resized_saved:
                resize_note = f"  已保存两个版本：原始大小和缩小版（文件名含 _resized 后缀）"
            return 1, resize_note

        for frame_idx in range(n_frames):
            img.seek(frame_idx)
            original_frame = img.convert("RGBA")
            resized_frame, note = resize_if_needed(original_frame)
            if note:
                resize_note = note
                # 保存原始大小版本
                original_frame.save(out_dir / f"{stem}_{frame_idx + 1:03d}.png", "PNG")
                # 保存缩小版本
                resized_frame.save(out_dir / f"{stem}_{frame_idx + 1:03d}_resized.png", "PNG")
                resized_saved = True
            else:
                original_frame.save(out_dir / f"{stem}_{frame_idx + 1:03d}.png", "PNG")

    if resized_saved:
        resize_note = f"  已保存两个版本：原始大小和缩小版（文件名含 _resized 后缀）"
    return n_frames, resize_note


def resolve_output_root(base_dir: Path, custom_output: str) -> Path:
    """根据优先级解析输出根目录：
    1) 指定输出路径（非空且可写目录）
    2) 原文件所在路径
    3) 桌面
    """
    if custom_output and custom_output.strip():
        p = Path(custom_output.strip())
        if p.is_dir():
            return p
        # 用户给的路径可能是带文件名的，尽量取父目录
        try:
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                return p
        except Exception:
            pass
    # 原路径
    if base_dir and base_dir.is_dir():
        return base_dir
    # 桌面
    desktop = Path.home() / "Desktop"
    if not desktop.is_dir():
        desktop = Path.home()
    return desktop


class ConverterApp:
    def __init__(self, root: tk.Tk, initial_paths: list[str] = None):
        self.root = root
        self.root.title(f"webp转换工具 {VERSION} | Author: Leooo")
        self.root.geometry("720x540")
        self.root.minsize(560, 420)
        
        # 设置窗口图标（兼容 PyInstaller 打包）
        base_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
        icon_path = base_dir / "webp_converter_icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # 等待区列表（每个元素是 (路径, 是否为文件夹)）
        self.queue: list[tuple[str, bool]] = []
        self.converting = False

        self._build_ui()

        # 命令行传入的路径进入等待区（不自动开始）
        self.initial_paths = initial_paths or []
        if self.initial_paths:
            for p in self.initial_paths:
                self._enqueue_path(p)
            self.log(f"已从命令行添加 {len(self.initial_paths)} 个路径到等待区，点击「开始转换」处理")

        if not _TKDND_AVAILABLE:
            self.log("[WARN] 未安装 tkinterdnd2，拖放不可用，请用点击空白处选择")

    # -------------------------- UI 构建 --------------------------
    def _build_ui(self) -> None:
        # 顶部说明
        tk.Label(
            self.root,
            text="拖入文件或文件夹到下方等待区，或点击「选择」添加；设置输出路径后点击「开始转换」",
            font=("Microsoft YaHei", 11),
        ).pack(pady=8)

        # 工具按钮区
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=4)

        tk.Button(btn_frame, text="清空等待区", command=self.clear_queue, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=5)

        # 等待区
        queue_frame = tk.Frame(self.root)
        queue_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(queue_frame, text="等待区（点击空白处选择文件，或直接拖拽文件/文件夹）：", anchor=tk.W, font=("Microsoft YaHei", 10)).pack(anchor=tk.W)

        list_frame = tk.Frame(queue_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.queue_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED, font=("Microsoft YaHei", 9))
        self.queue_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.queue_list.bind("<Button-1>", self._on_queue_click)
        self.queue_list.bind("<Delete>", lambda e: self.remove_selected())

        # 注册拖放目标（tkinterdnd2）- 注册到整个窗口，方便拖入
        if _TKDND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_dnd_drop)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.queue_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_list.config(yscrollcommand=scrollbar.set)

        # 输出路径
        out_frame = tk.Frame(self.root)
        out_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(out_frame, text="输出路径（留空=原路径，再退回桌面）：", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        self.out_var = tk.StringVar()
        out_entry = tk.Entry(out_frame, textvariable=self.out_var, font=("Microsoft YaHei", 9))
        out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(out_frame, text="浏览", command=self.browse_output, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)

        # 转换选项
        option_frame = tk.Frame(self.root)
        option_frame.pack(pady=4)

        self.gif_var = tk.BooleanVar(value=True)
        tk.Checkbutton(option_frame, text="转换为 GIF", variable=self.gif_var, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=8)

        self.png_var = tk.BooleanVar(value=False)
        tk.Checkbutton(option_frame, text="转换为 PNG（动图只取第一帧）", variable=self.png_var, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=8)

        self.split_var = tk.BooleanVar(value=False)
        tk.Checkbutton(option_frame, text="拆分帧（提取动图每一帧）", variable=self.split_var, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=8)

        # 开始按钮
        action_frame = tk.Frame(self.root)
        action_frame.pack(pady=6)
        self.start_btn = tk.Button(action_frame, text="开始转换", command=self.start_conversion, width=18, height=1, font=("Microsoft YaHei", 11), bg="#4CAF50", fg="white")
        self.start_btn.pack()

        # 日志区
        self.log_area = scrolledtext.ScrolledText(self.root, state=tk.DISABLED, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_area.tag_config("resize", foreground="red")

        # 底部状态
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=4)

        self.status_label = tk.Label(bottom_frame, text="就绪", anchor=tk.W, font=("Microsoft YaHei", 9))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            bottom_frame, text="Author: Leooo", anchor=tk.E,
            font=("Microsoft YaHei", 9), fg="#800080",
        ).pack(side=tk.RIGHT)

    # -------------------------- 等待区操作 --------------------------
    def _enqueue_path(self, raw_path: str) -> None:
        """把单个路径（文件或文件夹）加入等待区，去重"""
        p = raw_path.strip().strip('"')
        if not p:
            return
        path = Path(p)
        key = str(path.resolve())
        for existing, _ in self.queue:
            if str(Path(existing).resolve()) == key:
                return
        is_dir = path.is_dir()
        # 若不是文件夹也不是支持的文件，仍允许加入（转换时再判断）
        self.queue.append((p, is_dir))
        self._refresh_queue()

    def _refresh_queue(self) -> None:
        self.queue_list.delete(0, tk.END)
        for p, is_dir in self.queue:
            tag = "[文件夹]" if is_dir else "[文件]"
            self.queue_list.insert(tk.END, f"{tag} {p}")

    def _pick_via_dialog(self) -> None:
        """点击等待区空白时调用：弹小对话框让用户选「文件夹」或「文件」，
        再打开对应的选择器。"""
        win = tk.Toplevel(self.root)
        win.title("选择")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        # 居中
        win.update_idletasks()
        w, h = 260, 90
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(win, text="添加什么到等待区？", font=("Microsoft YaHei", 10)).pack(pady=(14, 6))

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=4)

        def pick_folder():
            win.destroy()
            folder = filedialog.askdirectory(title="选择文件夹")
            if folder:
                self._enqueue_path(folder)
                self.log(f"已添加文件夹到等待区: {folder}")

        def pick_files():
            win.destroy()
            files = filedialog.askopenfilenames(title="选择文件", filetypes=[("图片文件", "*.webp *.gif"), ("所有文件", "*.*")])
            for f in files:
                self._enqueue_path(f)
            if files:
                self.log(f"已添加 {len(files)} 个文件到等待区")

        tk.Button(btn_frame, text="选择文件夹", command=pick_folder, font=("Microsoft YaHei", 10), width=12).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="选择文件", command=pick_files, font=("Microsoft YaHei", 10), width=12).pack(side=tk.LEFT, padx=8)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def select_files(self) -> None:
        files = filedialog.askopenfilenames(filetypes=[("图片文件", "*.webp *.gif"), ("所有文件", "*.*")])
        for f in files:
            self._enqueue_path(f)
        if files:
            self.log(f"已添加 {len(files)} 个文件到等待区")

    def select_folders(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self._enqueue_path(folder)
            self.log(f"已添加文件夹到等待区: {folder}")

    def remove_selected(self) -> None:
        indices = list(self.queue_list.curselection())
        if not indices:
            return
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.queue):
                del self.queue[i]
        self._refresh_queue()

    def clear_queue(self) -> None:
        self.queue.clear()
        self._refresh_queue()

    def _on_queue_click(self, event: tk.Event) -> None:
        """点击等待区：若点击位置没有命中任何项（空白/列表为空），
        则打开选择对话框（先选文件夹，取消则选文件）。"""
        nearest = self.queue_list.nearest(event.y)
        bbox = self.queue_list.bbox(nearest)
        hit = False
        if bbox:
            x1, y1, width, height = bbox
            if x1 <= event.x <= x1 + width and y1 <= event.y <= y1 + height:
                hit = True
        if not hit:
            self._pick_via_dialog()

    def browse_output(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.out_var.set(folder)

    # -------------------------- 拖放支持 --------------------------
    def _on_dnd_drop(self, event) -> None:
        """tkinterdnd2 拖放回调：event.data 是被拖入的路径列表字符串。
        Windows 下带空格的路径会用花括号包裹，这里做解析。"""
        raw = event.data or ""
        # 解析形如 "{C:\path with space} C:\plain\path" 的字符串
        paths: list[str] = []
        current = ""
        in_braces = False
        for ch in raw:
            if ch == "{":
                in_braces = True
                if current.strip():
                    paths.append(current.strip())
                    current = ""
                continue
            if ch == "}":
                in_braces = False
                paths.append(current)
                current = ""
                continue
            if ch == " " and not in_braces:
                if current.strip():
                    paths.append(current.strip())
                    current = ""
                continue
            current += ch
        if current.strip():
            paths.append(current.strip())

        added = 0
        for p in paths:
            before = len(self.queue)
            self._enqueue_path(p)
            if len(self.queue) > before:
                added += 1
        if added:
            self.log(f"拖入并添加 {added} 个路径到等待区")

    # -------------------------- 日志/状态 --------------------------
    def log(self, message: str) -> None:
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def log_red(self, message: str) -> None:
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n", "resize")
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def set_status(self, message: str) -> None:
        self.status_label.config(text=message)

    # -------------------------- 转换流程 --------------------------
    def start_conversion(self) -> None:
        if self.converting:
            return
        if not self.queue:
            messagebox.showinfo("提示", "等待区为空，请先拖入或选择文件/文件夹")
            return
        if not (self.gif_var.get() or self.png_var.get() or self.split_var.get()):
            messagebox.showinfo("提示", "请至少选择一种转换方式")
            return

        self.converting = True
        self.start_btn.config(state=tk.DISABLED, text="转换中...")
        self.set_status("转换中...")
        thread = threading.Thread(target=self._run_conversion, daemon=True)
        thread.start()

    def _collect_files(self) -> list[Path]:
        """把等待区里的文件/文件夹展开为具体的 webp/gif 文件列表"""
        files: list[Path] = []
        for p, is_dir in self.queue:
            path = Path(p.strip('"'))
            if path.is_dir():
                for f in sorted(path.iterdir()):
                    if f.is_file() and f.suffix.lower() in (".webp", ".gif"):
                        files.append(f)
            elif path.is_file() and path.suffix.lower() in (".webp", ".gif"):
                files.append(path)
            else:
                self.root.after(0, lambda pp=p: self.log(f"[SKIP] 不支持的路径: {pp}"))
        return files

    def _run_conversion(self) -> None:
        custom_output = self.out_var.get()
        do_gif = self.gif_var.get()
        do_png = self.png_var.get()
        do_split = self.split_var.get()

        total_success = 0
        total_fail = 0

        files = self._collect_files()
        if not files:
            self.root.after(0, lambda: self.log("[INFO] 等待区中没有 webp/gif 文件"))

        for src_file in files:
            src_file = src_file.resolve()
            dir_path = src_file.parent

            # 输出根目录优先级：指定路径 > 原路径 > 桌面
            out_root = resolve_output_root(dir_path, custom_output)
            self.root.after(0, lambda f=src_file.name, o=out_root: self.log(f"处理: {f}  ->  输出: {o}"))

            file_ok = True

            if do_gif:
                try:
                    output_dir = out_root / "newgif"
                    output_file = output_dir / src_file.with_suffix(".gif").name
                    resize_note = convert_webp_to_gif(str(src_file), str(output_file))
                    self.root.after(0, lambda f=src_file.name: self.log(f"[GIF] {f}"))
                    if resize_note:
                        self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                except Exception as e:
                    self.root.after(0, lambda f=src_file.name, err=e: self.log(f"[FAIL-GIF] {f}: {err}"))
                    file_ok = False

            if do_png:
                try:
                    output_dir = out_root / "newpng"
                    output_file = output_dir / src_file.with_suffix(".png").name
                    resize_note = convert_webp_to_png(str(src_file), str(output_file))
                    self.root.after(0, lambda f=src_file.name: self.log(f"[PNG] {f}"))
                    if resize_note:
                        self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                except Exception as e:
                    self.root.after(0, lambda f=src_file.name, err=e: self.log(f"[FAIL-PNG] {f}: {err}"))
                    file_ok = False

            if do_split:
                try:
                    output_dir = out_root / "frames"
                    sub_dir = output_dir / src_file.stem
                    n_frames, resize_note = extract_frames(str(src_file), str(sub_dir))
                    self.root.after(0, lambda f=src_file.name, n=n_frames: self.log(f"[SPLIT] {f} -> {n} 帧"))
                    if resize_note:
                        self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                except Exception as e:
                    self.root.after(0, lambda f=src_file.name, err=e: self.log(f"[FAIL-SPLIT] {f}: {err}"))
                    file_ok = False

            if file_ok:
                total_success += 1
            else:
                total_fail += 1

        self.root.after(0, self._finish_conversion, total_success, total_fail)

    def _finish_conversion(self, total_success: int, total_fail: int) -> None:
        self.converting = False
        self.start_btn.config(state=tk.NORMAL, text="开始转换")
        self.set_status(f"完成：成功 {total_success} 个，失败 {total_fail} 个")
        if total_fail > 0:
            messagebox.showwarning("转换完成", f"成功 {total_success} 个，失败 {total_fail} 个\n请查看日志了解失败文件")
        else:
            messagebox.showinfo("转换完成", f"成功 {total_success} 个，失败 {total_fail} 个")


def main():
    initial_paths = [arg.strip('"') for arg in sys.argv[1:] if arg.strip('"')]

    if _TKDND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = ConverterApp(root, initial_paths=initial_paths)
    root.mainloop()


if __name__ == "__main__":
    main()
