"""PDF Editör Pro app icon generator.

The Store logo (images/store_logo_1080x1080.png) has fine detail ("editor Pro",
"MKBSOFT", the pen arrow) that turns into a blur at taskbar/desktop sizes. This
draws a simplified version in the same colours — navy tile, white page, bold
teal "PDF" — that stays readable down to 16 px.

    python make_icon.py        -> writes icon.ico (16..256) and a preview PNG
"""
import os

from PIL import Image, ImageDraw, ImageFont

NAVY = (15, 28, 47, 255)
TEAL = (12, 121, 142, 255)
WHITE = (247, 248, 250, 255)
FOLD = (205, 214, 226, 255)

ROOT = os.path.dirname(os.path.abspath(__file__))
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def _font(px):
    for name in ('segoeuib.ttf', 'arialbd.ttf'):
        try:
            return ImageFont.truetype(os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', name), px)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw(s, tile=True, tiny=False):
    """Draw the icon at s x s. tile=False leaves the background transparent.
    tiny=True (final size <= 20 px): bigger page and a solid band instead of text."""
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tile:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.20), fill=NAVY)

    # Page with folded top-right corner
    if tiny:
        l, t, r, b = s * 0.16, s * 0.06, s * 0.84, s * 0.94
    else:
        l, t, r, b = s * 0.20, s * 0.10, s * 0.80, s * 0.90
    fold = s * 0.18
    d.polygon([(l, t), (r - fold, t), (r, t + fold), (r, b), (l, b)], fill=WHITE)
    d.polygon([(r - fold, t), (r, t + fold), (r - fold, t + fold)], fill=FOLD)

    if tiny:
        d.rectangle([l + s * 0.08, t + (b - t) * 0.42, r - s * 0.08, t + (b - t) * 0.70], fill=TEAL)
        return img

    # Big "PDF", as wide as the page allows
    text = 'PDF'
    target_w = (r - l) * 0.86
    px = int(s * 0.30)
    font = _font(px)
    w = d.textbbox((0, 0), text, font=font)[2]
    font = _font(max(1, int(px * target_w / w)))
    bx0, by0, bx1, by1 = d.textbbox((0, 0), text, font=font)
    cx, cy = (l + r) / 2, t + (b - t) * 0.60
    d.text((cx - (bx1 - bx0) / 2 - bx0, cy - (by1 - by0) / 2 - by0), text, font=font, fill=TEAL)

    # Teal underline accent
    lw = max(1, round(s * 0.045))
    y = cy + (by1 - by0) / 2 + s * 0.06
    d.rectangle([l + s * 0.08, y, r - s * 0.08, y + lw], fill=TEAL)
    return img


def make_icon(size, tile=True):
    """Render at 4x and downsample, so edges are anti-aliased at every size."""
    big = _draw(size * 4 if size < 256 else size, tile, tiny=size <= 20)
    return big.resize((size, size), Image.LANCZOS) if big.size[0] != size else big


def write_ico(path=os.path.join(ROOT, 'icon.ico')):
    imgs = [make_icon(sz) for sz in ICO_SIZES]
    imgs[-1].save(path, format='ICO', sizes=[(sz, sz) for sz in ICO_SIZES],
                  append_images=imgs[:-1])
    return path


def write_static():
    """Window icon, favicons and the header logo used by the app itself."""
    static = os.path.join(ROOT, 'static')
    write_ico(os.path.join(static, 'app-icon.ico'))
    write_ico(os.path.join(static, 'favicon.ico'))
    for size, name in ((16, 'favicon-16.png'), (32, 'favicon-32.png'), (64, 'favicon.png'),
                       (96, 'app-icon-96.png')):
        make_icon(size).save(os.path.join(static, name))


if __name__ == '__main__':
    print('wrote', write_ico())
    write_static()
    # Preview: every size on dark and light backgrounds, scaled 1:1
    sizes = [16, 24, 32, 48, 64, 128]
    W = sum(sizes) + 20 * (len(sizes) + 1)
    prev = Image.new('RGBA', (W, 2 * 128 + 60), (255, 255, 255, 255))
    ImageDraw.Draw(prev).rectangle([0, 0, W, 128 + 30], fill=(32, 32, 36, 255))
    x = 20
    for sz in sizes:
        ic = make_icon(sz)
        prev.paste(ic, (x, 15 + 128 - sz), ic)
        prev.paste(ic, (x, 128 + 45 + 128 - sz), ic)
        x += sz + 20
    out = os.path.join(os.environ.get('ICON_PREVIEW_DIR', ROOT), 'icon_preview.png')
    prev.save(out)
    print('preview', out)
