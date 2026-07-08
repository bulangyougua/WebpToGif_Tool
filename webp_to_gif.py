#!/usr/bin/env python3
"""
WebP to GIF Converter
带图形界面，支持双击运行和拖拽文件夹
"""

import sys
import threading
from pathlib import Path
from PIL import Image

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox

MAX_SIZE = 1024
VERSION = "V1.0.1"


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

            for frame_idx in range(n_frames):
                img.seek(frame_idx)
                frame, note = resize_if_needed(img.convert("RGBA"))
                if note:
                    resize_note = note
                frame = frame.convert("P", palette=Image.ADAPTIVE, colors=256)
                frames.append(frame)
                duration = img.info.get("duration", 100)
                durations.append(duration)

            frames[0].save(
                output_file,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=img.info.get("loop", 0),
                optimize=True,
            )
        else:
            if img.mode in ("RGBA", "P"):
                img, resize_note = resize_if_needed(img.convert("RGBA"))
                img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
            elif img.mode != "P":
                img, resize_note = resize_if_needed(img.convert("RGB"))

            img.save(output_file, "GIF", optimize=True)

    return resize_note


class ConverterApp:
    def __init__(self, root: tk.Tk, initial_paths: list[str] = None):
        self.root = root
        self.root.title("WebP to GIF 转换器")
        self.root.geometry("600x400")
        self.root.minsize(500, 300)

        self.label = tk.Label(root, text="选择一个或多个文件夹，转换其中的 webp 文件", font=("Microsoft YaHei", 11))
        self.label.pack(pady=10)

        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=5)

        self.select_btn = tk.Button(self.btn_frame, text="选择文件夹", command=self.select_folders, font=("Microsoft YaHei", 10))
        self.select_btn.pack(side=tk.LEFT, padx=5)

        self.bottom_frame = tk.Frame(root)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        self.status_label = tk.Label(self.bottom_frame, text="就绪", anchor=tk.W, font=("Microsoft YaHei", 9))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.version_label = tk.Label(
            self.bottom_frame,
            text=f"{VERSION} | Author: Leooo",
            anchor=tk.E,
            font=("Microsoft YaHei", 9),
            fg="#800080",
        )
        self.version_label.pack(side=tk.RIGHT)

        self.log_area = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_area.tag_config("resize", foreground="red")

        self.initial_paths = initial_paths or []

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

    def select_folders(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.process_paths([folder])

    def process_paths(self, paths: list[str]) -> None:
        self.select_btn.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._run_conversion, args=(paths,), daemon=True)
        thread.start()

    def _run_conversion(self, paths: list[str]) -> None:
        total_success = 0
        total_fail = 0

        for folder_path in paths:
            folder_path = folder_path.strip('"')
            dir_path = Path(folder_path)

            if not dir_path.is_dir():
                self.root.after(0, lambda p=folder_path: self.log(f"[SKIP] 不是文件夹: {p}"))
                continue

            self.root.after(0, lambda p=folder_path: self.log(f"处理文件夹: {p}"))
            output_dir = dir_path / "newgif"
            webp_files = sorted(
                {p.resolve() for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() == ".webp"}
            )

            if not webp_files:
                self.root.after(0, lambda p=folder_path: self.log(f"[INFO] 没有 webp 文件: {p}"))
                continue

            for webp_file in webp_files:
                output_file = output_dir / webp_file.with_suffix(".gif").name
                try:
                    resize_note = convert_webp_to_gif(str(webp_file), str(output_file))
                    self.root.after(0, lambda f=webp_file.name: self.log(f"[OK] {f}"))
                    if resize_note:
                        self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                    total_success += 1
                except Exception as e:
                    self.root.after(0, lambda f=webp_file.name, err=e: self.log(f"[FAIL] {f}: {err}"))
                    total_fail += 1

            self.root.after(0, lambda p=output_dir: self.log(f"[INFO] 输出目录: {p}"))
            self.root.after(0, self.log, "")

        def finish():
            self.set_status(f"完成：成功 {total_success} 个，失败 {total_fail} 个")
            self.select_btn.config(state=tk.NORMAL)
            if total_fail > 0:
                messagebox.showwarning("转换完成", f"成功 {total_success} 个，失败 {total_fail} 个\n请查看日志了解失败文件")
            else:
                messagebox.showinfo("转换完成", f"成功 {total_success} 个，失败 {total_fail} 个")

        self.root.after(0, finish)

    def run_initial(self) -> None:
        if self.initial_paths:
            self.process_paths(self.initial_paths)


def main():
    initial_paths = [arg.strip('"') for arg in sys.argv[1:] if arg.strip('"')]

    root = tk.Tk()
    app = ConverterApp(root, initial_paths=initial_paths)

    if initial_paths:
        root.after(100, app.run_initial)

    root.mainloop()


if __name__ == "__main__":
    main()
