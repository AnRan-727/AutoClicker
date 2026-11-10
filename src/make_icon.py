"""生成应用图标：AppIcon.png、AppIcon.ico（Windows）、AppIcon.icns（macOS，需 iconutil）
用法：python make_icon.py [输出目录，默认 assets]"""
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"
os.makedirs(OUT, exist_ok=True)
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角渐变底
bg = Image.new("RGBA", (S, S))
bd = ImageDraw.Draw(bg)
for y in range(S):
    t = y / S
    bd.line([(0, y), (S, y)], fill=(int(30 + 20 * t), int(120 - 40 * t), int(235 - 60 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([90, 90, S - 90, S - 90], radius=190, fill=255)
img.paste(bg, (0, 0), mask)

# 识别框 + 准星
c, r = S // 2, 250
w = 34
d.ellipse([c - r, c - r, c + r, c + r], outline="white", width=w)
d.ellipse([c - 60, c - 60, c + 60, c + 60], fill="white")
for x0, y0, x1, y1 in [(c, c - r - 90, c, c - r + 70), (c, c + r - 70, c, c + r + 90),
                       (c - r - 90, c, c - r + 70, c), (c + r - 70, c, c + r + 90, c)]:
    d.line([x0, y0, x1, y1], fill="white", width=w)

# 鼠标指针
p = [(600, 560), (600, 860), (670, 790), (720, 900), (770, 878), (720, 770), (815, 770)]
d.polygon(p, fill=(255, 196, 0), outline=(40, 40, 40))
d.line(p + [p[0]], fill=(40, 40, 40), width=12)

img.save(os.path.join(OUT, "AppIcon.png"))

iconset = os.path.join(OUT, "AppIcon.iconset")
shutil.rmtree(iconset, ignore_errors=True)
os.makedirs(iconset)
for size in (16, 32, 128, 256, 512):
    img.resize((size, size), Image.LANCZOS).save(f"{iconset}/icon_{size}x{size}.png")
    img.resize((size * 2, size * 2), Image.LANCZOS).save(f"{iconset}/icon_{size}x{size}@2x.png")
if shutil.which("iconutil"):
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(OUT, "AppIcon.icns")], check=True)
    print(f"图标已生成 {OUT}/AppIcon.icns")
else:
    print("未找到 iconutil（非 macOS），跳过 .icns")

img.save(os.path.join(OUT, "AppIcon.ico"),
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"图标已生成 {OUT}/AppIcon.ico")
