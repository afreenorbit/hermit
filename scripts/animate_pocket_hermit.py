"""Bake Pocket Hermit's illustrated poses into animated WebP using Pillow and NumPy."""

from math import cos, pi, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from base64 import b64encode


ASSETS = Path(__file__).resolve().parents[1] / "map/public/pocket-hermit"
# Landmarks in the original character sheet, before cropping the pose PNGs.
POSES = {
    "visiting": ((280, 125), [(519, 713), (718, 713)], [(542, 467), (792, 441)],
                 [(603, 345), (736, 309)], (584, 568), (397, 616), (453, 239)),
    "arriving": ((56, 803), [(174, 1161), (289, 1162)], [(172, 1026), (333, 993)],
                 [(214, 965), (276, 936)], (207, 1095), (127, 1121), (133, 925)),
    "sleeping": ((431, 815), [], [(639, 1055), (705, 1039)],
                 [(613, 1011), (682, 998)], (605, 1100), (521, 1119), (555, 961)),
    "away": ((829, 820), [(959, 1152), (1097, 1149)], [], [],
             (1015, 1062), (953, 1078), (925, 916)),
}


def cutout(name):
    art = Image.open(Path(__file__).parent / "pocket_hermit_art" / f"{name}.png").convert("RGB")
    # The continuous brown ink contour encloses the character. Seed its interior
    # from the cup so detached punctuation and the printed shadow drop out.
    rgb = np.asarray(art)
    ink = Image.fromarray(((rgb[:,:,1] < 153) & (rgb[:,:,0] < 197)).astype("uint8")*255)
    ink = ink.filter(ImageFilter.MaxFilter(3))
    ImageDraw.floodfill(ink, (0, 0), 100)
    solid = ink.point(lambda n: 0 if n == 100 else 255)
    ImageDraw.floodfill(solid, (art.width//2, int(art.height*.72)), 128)
    alpha = solid.point(lambda n: 255 if n == 128 else 0)
    art.putalpha(alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(.55)))
    return art


def animate(name, rig):
    origin, feet, hands, eyes, cup, charm, leaf = rig
    pose = cutout(name)
    if name == "arriving":
        patch = pose.crop((175,149,199,184))
        mask = Image.new("L", patch.size)
        ImageDraw.Draw(mask).ellipse((1,2,23,33), fill=255)
        pose.paste(patch, (193,150), mask.filter(ImageFilter.GaussianBlur(1)))
    scale = 320 / max(pose.size)
    pose = pose.resize(tuple(round(v * scale) for v in pose.size), Image.Resampling.LANCZOS)
    pixels = np.asarray(pose)
    y, x = np.indices(pixels.shape[:2], dtype=np.float32)
    x = x / scale + origin[0]
    y = y / scale + origin[1]
    size = 1.9 if name == "visiting" else 1
    walking = name == "away"
    frames = []
    count = 40 if walking else 60
    for frame in range(count):
        t = 2 * pi * frame / count
        step = sin(2 * t) * (min(1, 3*(1-cos(t))) if walking else 1)
        smile = min(1, max(0, (1-cos(t)-.22)*1.6))
        sx, sy = x.copy(), y.copy()

        def influence(point, rx, ry):
            return np.exp(-((x - point[0]) / (rx * size)) ** 2
                          - ((y - point[1]) / (ry * size)) ** 2)

        def move(point, width, height, dx, dy):
            weight = influence(point, width, height) * size
            sx[:] -= weight * dx
            sy[:] -= weight * dy

        # The cup rocks about its centre while the charm swings slightly later.
        angle = (0.055 if walking else 0.024) * sin(2 * t if walking else t)
        shell = influence(cup, 135, 90)
        sx += shell * (y - cup[1]) * angle
        sy -= shell * (x - cup[0]) * angle
        move(charm, 26, 31, 8 * sin(2 * t - 0.5), 1.5 * step)
        move(leaf, 48, 34, 7 * sin(t), 5 * cos(t))
        for i, foot in enumerate(feet):
            swing = step * (-1) ** i
            stride = 9 if walking else 1
            move(foot, 23, 17, stride * swing, -stride * max(0, swing))
        for i, hand in enumerate(hands):
            wave = sin(2 * t + i * pi)
            lift = {"arriving": 6, "sleeping": 2, "visiting": 6, "away": 0}[name]
            move(hand, 20, 19, lift * 0.55 * wave, -lift * (1 + wave) / 2)
        for eye in eyes:
            if name == "sleeping":
                move(eye, 37, 28, 0, 4 * sin(t))
                continue
            # Compress the painted eye into a line, stretching adjacent face
            # colour into the exposed area. Both eyes blink together.
            blink = max(0, 1 - abs(frame / count - 0.73) / 0.075)
            h = 12 * size
            delta = y - eye[1]
            lid = h * (1 - 0.92 * blink)
            distance = np.abs(delta)
            remap = np.interp(distance, [0, lid, 2.5*h], [0, h, 2.5*h])
            mask = np.clip(2 - abs(x - eye[0]) / (11*size), 0, 1)
            sy += np.where(distance < 2.5*h, (remap-distance)*np.sign(delta)*mask, 0)
            move(eye, 13, 16, 2.8 * sin(t), 0)
        if name == "sleeping":
            move((642, 988), 102, 72, 0, 6 * sin(t))
            move((743, 863), 55, 32, 3 * sin(t), -7 * sin(t))
        if name == "visiting":
            # Relax the open grin between greetings.
            sy += (y-351) * .85 * smile * influence((678,351), 20, 23)

        # Bilinear texture sampling preserves the original painted details.
        u = np.clip((sx-origin[0])*scale, 0, pose.width-1)
        v = np.clip((sy-origin[1])*scale, 0, pose.height-1)
        a, b = u.astype(int), v.astype(int)
        c, d = np.minimum(a+1, pose.width-1), np.minimum(b+1, pose.height-1)
        fx, fy = (u-a)[..., None], (v-b)[..., None]
        rgb = ((pixels[b,a]*(1-fx) + pixels[b,c]*fx)*(1-fy)
               + (pixels[d,a]*(1-fx) + pixels[d,c]*fx)*fy)
        body = Image.fromarray(rgb.astype("uint8"))
        if name == "arriving":
            # An open O softens into a curved smile. Draw in sheet coordinates.
            def pt(px, py):
                return ((px-origin[0])*scale, (py-origin[1])*scale)
            pen = ImageDraw.Draw(body)
            half = 4 + 5*smile
            height = 7*(1-smile)
            curve = [pt(261+half*u, 970+4*smile*(1-u*u)-height*(1-u*u)**.5) for u in np.linspace(-1,1,25)]
            lower = [pt(261+half*u, 970+4*smile*(1-u*u)+height*(1-u*u)**.5) for u in np.linspace(1,-1,25)]
            pen.polygon(curve+lower, fill="#a65d36")
            pen.line(curve, fill="#985631", width=2)
            dx, dy = 12+2*sin(t), 2-3*smile
            def letter(points):
                return [pt(px+dx, py+dy) for px,py in points]
            corners = [(102,1008),(151,1001),(157,1032),(108,1040)]
            pen.polygon(letter(corners), fill="#fff0ce", outline="#88572e", width=2)
            pen.line(letter([corners[0],(130,1023),corners[1]]), fill="#b78654", width=2)
            pen.ellipse([pt(127+dx,1018+dy),pt(134+dx,1025+dy)], fill="#da896b")
        shadow = Image.new("RGBA", body.size)
        box = body.getchannel("A").getbbox()
        left, top, right, base = box
        width = right-left
        ImageDraw.Draw(shadow).ellipse((left+.14*width, base-6, right-.14*width, base+3),
                                       fill=(92,65,45,50))
        shadow = shadow.filter(ImageFilter.GaussianBlur(2.4))
        shadow.alpha_composite(body)
        frames.append(shadow)
    frames[0].save(ASSETS / f"{name}.png")
    frames[0].save(ASSETS / f"{name}.webp", save_all=True, append_images=frames[1:],
                   duration=50, loop=0, quality=86, method=3)
    # Preserve the original standalone SVG links, including reduced motion.
    def embedded(ext):
        return b64encode((ASSETS / f"{name}.{ext}").read_bytes()).decode()
    (ASSETS / f"{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {pose.width} {pose.height}">'
        '<style>.still{display:none}@media(prefers-reduced-motion:reduce){.moving{display:none}.still{display:inline}}</style>'
        + ''.join(f'<image class="{cls}" width="{pose.width}" height="{pose.height}" '
                  f'href="data:image/{ext};base64,{embedded(ext)}"/>'
                  for cls,ext in [('moving','webp'),('still','png')]) + '</svg>')


if __name__ == "__main__":
    for state, landmarks in POSES.items():
        animate(state, landmarks)
