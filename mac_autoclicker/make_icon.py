"""生成应用图标 assets/AppIcon.icns（需在 macOS 上运行，依赖 iconutil）"""
import os
import shutil
import subprocess

from PIL import Image, ImageDraw

os.makedirs("assets", exist_ok=True)
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

img.save("assets/AppIcon.png")

iconset = "assets/AppIcon.iconset"
shutil.rmtree(iconset, ignore_errors=True)
os.makedirs(iconset)
for size in (16, 32, 128, 256, 512):
    img.resize((size, size), Image.LANCZOS).save(f"{iconset}/icon_{size}x{size}.png")
    img.resize((size * 2, size * 2), Image.LANCZOS).save(f"{iconset}/icon_{size}x{size}@2x.png")
if shutil.which("iconutil"):
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", "assets/AppIcon.icns"], check=True)
    print("图标已生成 assets/AppIcon.icns")
else:
    print("未找到 iconutil（非 macOS），仅生成 PNG")
