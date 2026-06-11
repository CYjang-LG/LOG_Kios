# 아이콘 생성 스크립트 (Termux에서 한 번만 실행)
# cd ~/LOG_Kios/static && python gen_icon.py

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'Pillow'], check=True)
    from PIL import Image, ImageDraw, ImageFont

import os

def make_icon(size, filename):
    img = Image.new('RGB', (size, size), color=(13, 43, 107))
    draw = ImageDraw.Draw(img)
    # 흰 원
    margin = size // 6
    draw.ellipse([margin, margin, size - margin, size - margin], fill=(255, 255, 255))
    # 'L' 텍스트
    try:
        font = ImageFont.truetype('/system/fonts/NotoSansCJK-Regular.ttc', size // 3)
    except:
        font = ImageFont.load_default()
    text = 'L'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2 - size * 0.03), text, fill=(13, 43, 107), font=font)
    img.save(filename)
    print(f'✅ {filename} 생성 완료')

make_icon(192, 'icon-192.png')
make_icon(512, 'icon-512.png')
print('아이콘 생성 완료! 브라우저에서 홈화면에 추가 후 실행하세요.')
