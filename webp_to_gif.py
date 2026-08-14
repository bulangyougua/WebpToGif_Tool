#!/usr/bin/env python3
"""
WebP/GIF Converter
带图形界面，支持双击运行和拖拽文件夹
支持 WebP 和 GIF 格式的转换与帧提取
"""

import sys
import threading
from pathlib import Path
from PIL import Image

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox

MAX_SIZE = 1024
VERSION = "V1.2.0"


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


def convert_webp_to_png(input_path: str, output_path: str) -> str | None:
    """将单个 WebP 文件转换为 PNG，若发生缩放则返回说明文字"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    resize_note = None

    with Image.open(input_path) as img:
        is_animated = getattr(img, "is_animated", False)
        n_frames = getattr(img, "n_frames", 1)

        if is_animated and n_frames > 1:
            # 动图只取第一帧转为 PNG
            img.seek(0)
            frame, note = resize_if_needed(img.convert("RGBA"))
            if note:
                resize_note = note
            frame.save(output_file, "PNG")
        else:
            if img.mode in ("RGBA", "P"):
                img, resize_note = resize_if_needed(img.convert("RGBA"))
            else:
                img, resize_note = resize_if_needed(img.convert("RGB"))
            img.save(output_file, "PNG")

    return resize_note


def extract_frames(input_path: str, output_dir: str) -> tuple[int, str | None]:
    """将动图（WebP 或 GIF）的每一帧提取为单独的 PNG 文件，返回 (帧数, 缩放说明)"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resize_note = None
    stem = Path(input_path).stem

    with Image.open(input_path) as img:
        is_animated = getattr(img, "is_animated", False)
        n_frames = getattr(img, "n_frames", 1)

        if not is_animated or n_frames <= 1:
            # 静态图直接保存一帧
            frame, note = resize_if_needed(img.convert("RGBA"))
            if note:
                resize_note = note
            frame.save(out_dir / f"{stem}_001.png", "PNG")
            return 1, resize_note

        for frame_idx in range(n_frames):
            img.seek(frame_idx)
            frame, note = resize_if_needed(img.convert("RGBA"))
            if note:
                resize_note = note
            frame.save(out_dir / f"{stem}_{frame_idx + 1:03d}.png", "PNG")

    return n_frames, resize_note


class ConverterApp:
    def __init__(self, root: tk.Tk, initial_paths: list[str] = None):
        self.root = root
        self.root.title("WebP/GIF 转换器")
        self.root.geometry("600x400")
        self.root.minsize(500, 300)

        self.label = tk.Label(root, text="选择一个或多个文件夹，转换其中的 webp/gif 文件", font=("Microsoft YaHei", 11))
        self.label.pack(pady=10)

        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=5)

        self.select_btn = tk.Button(self.btn_frame, text="选择文件夹", command=self.select_folders, font=("Microsoft YaHei", 10))
        self.select_btn.pack(side=tk.LEFT, padx=5)

        self.option_frame = tk.Frame(root)
        self.option_frame.pack(pady=5)

        self.gif_var = tk.BooleanVar(value=True)
        self.gif_cb = tk.Checkbutton(
            self.option_frame, text="转换为 GIF", variable=self.gif_var,
            font=("Microsoft YaHei", 10),
        )
        self.gif_cb.pack(side=tk.LEFT, padx=10)

        self.png_var = tk.BooleanVar(value=False)
        self.png_cb = tk.Checkbutton(
            self.option_frame, text="转换为 PNG（动图只取第一帧）", variable=self.png_var,
            font=("Microsoft YaHei", 10),
        )
        self.png_cb.pack(side=tk.LEFT, padx=10)

        self.split_var = tk.BooleanVar(value=False)
        self.split_cb = tk.Checkbutton(
            self.option_frame, text="拆分帧（提取动图每一帧）", variable=self.split_var,
            font=("Microsoft YaHei", 10),
        )
        self.split_cb.pack(side=tk.LEFT, padx=10)

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

    def _set_cb_state(self, state: str) -> None:
        self.gif_cb.config(state=state)
        self.png_cb.config(state=state)
        self.split_cb.config(state=state)

    def process_paths(self, paths: list[str]) -> None:
        self.select_btn.config(state=tk.DISABLED)
        self._set_cb_state(tk.DISABLED)
        thread = threading.Thread(target=self._run_conversion, args=(paths,), daemon=True)
        thread.start()

    def _run_conversion(self, paths: list[str]) -> None:
        total_success = 0
        total_fail = 0
        do_gif = self.gif_var.get()
        do_png = self.png_var.get()
        do_split = self.split_var.get()

        for folder_path in paths:
            folder_path = folder_path.strip('"')
            dir_path = Path(folder_path)

            if not dir_path.is_dir():
                self.root.after(0, lambda p=folder_path: self.log(f"[SKIP] 不是文件夹: {p}"))
                continue

            self.root.after(0, lambda p=folder_path: self.log(f"处理文件夹: {p}"))

            supported_files = sorted(
                {p.resolve() for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in (".webp", ".gif")}
            )

            if not supported_files:
                self.root.after(0, lambda p=folder_path: self.log(f"[INFO] 没有 webp/gif 文件: {p}"))
                continue

            for webp_file in supported_files:
                file_ok = True

                if do_gif:
                    try:
                        output_dir = dir_path / "newgif"
                        output_file = output_dir / webp_file.with_suffix(".gif").name
                        resize_note = convert_webp_to_gif(str(webp_file), str(output_file))
                        self.root.after(0, lambda f=webp_file.name: self.log(f"[GIF] {f}"))
                        if resize_note:
                            self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                    except Exception as e:
                        self.root.after(0, lambda f=webp_file.name, err=e: self.log(f"[FAIL-GIF] {f}: {err}"))
                        file_ok = False

                if do_png:
                    try:
                        output_dir = dir_path / "newpng"
                        output_file = output_dir / webp_file.with_suffix(".png").name
                        resize_note = convert_webp_to_png(str(webp_file), str(output_file))
                        self.root.after(0, lambda f=webp_file.name: self.log(f"[PNG] {f}"))
                        if resize_note:
                            self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                    except Exception as e:
                        self.root.after(0, lambda f=webp_file.name, err=e: self.log(f"[FAIL-PNG] {f}: {err}"))
                        file_ok = False

                if do_split:
                    try:
                        output_dir = dir_path / "frames"
                        sub_dir = output_dir / webp_file.stem
                        n_frames, resize_note = extract_frames(str(webp_file), str(sub_dir))
                        self.root.after(0, lambda f=webp_file.name, n=n_frames: self.log(f"[SPLIT] {f} -> {n} 帧"))
                        if resize_note:
                            self.root.after(0, lambda msg=resize_note: self.log_red(msg))
                    except Exception as e:
                        self.root.after(0, lambda f=webp_file.name, err=e: self.log(f"[FAIL-SPLIT] {f}: {err}"))
                        file_ok = False

                if file_ok:
                    total_success += 1
                else:
                    total_fail += 1

            if do_gif:
                self.root.after(0, lambda p=dir_path / "newgif": self.log(f"[INFO] GIF 输出: {p}"))
            if do_png:
                self.root.after(0, lambda p=dir_path / "newpng": self.log(f"[INFO] PNG 输出: {p}"))
            if do_split:
                self.root.after(0, lambda p=dir_path / "frames": self.log(f"[INFO] 帧输出: {p}"))
            self.root.after(0, self.log, "")

        def finish():
            self.set_status(f"完成：成功 {total_success} 个，失败 {total_fail} 个")
            self.select_btn.config(state=tk.NORMAL)
            self._set_cb_state(tk.NORMAL)
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
