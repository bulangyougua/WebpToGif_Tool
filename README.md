# WebP to GIF 转换工具

简单的 Python 工具，将 WebP 图片（支持动画）转换为 GIF 格式。

## 安装依赖

```bash
pip install Pillow
```

## 使用方法

### 1. 转换单个文件（同目录输出）

```bash
python webp_to_gif.py 图片.webp
```

### 2. 指定输出文件路径

```bash
python webp_to_gif.py -o 输出.gif 图片.webp
```

### 3. 指定输出目录

```bash
python webp_to_gif.py -d C:\Users\14439\Desktop\res 图片.webp
```

### 4. 批量转换目录到指定输出目录

```bash
python webp_to_gif.py -d C:\Users\14439\Desktop\res 文件夹路径
```

### 5. 拖拽转换（Windows）

直接将 `.webp` 文件或文件夹拖拽到 `拖拽转换.bat` 上，自动保存到 `C:\Users\14439\Desktop\res`。

如需修改输出目录，用文本编辑器打开 `拖拽转换.bat`，修改第一行的 `OUTPUT_DIR` 变量。

## 功能特点

- 支持静态 WebP 转 GIF
- 支持动画 WebP 转动画 GIF（保留帧率和循环设置）
- 支持透明通道
- 支持批量转换
- 自动调色板优化
- 支持自定义输出目录
