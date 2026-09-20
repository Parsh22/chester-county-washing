"""
Turn a side-by-side "before | after" photo into two web-ready images.

    python import_photos.py "~/Desktop/Before&After 1.png" deck-post
    python import_photos.py <source> <slug> [--no-split]

Phone screenshots of a before/after pair usually come out as one wide image
with a white gutter down the middle. This finds that gutter, splits the image
in two, trims the edges and writes optimised JPEGs into static/photos/jobs/.

Pass --no-split if the source is already a single photo.

Pillow is only needed to run this script, not to run the site, which is why
it isn't in requirements.txt.
"""

import io
import pathlib
import sys

from PIL import Image

OUT = pathlib.Path(__file__).parent / "static" / "photos" / "jobs"

# What the finished images should be. 4:3 keeps phone photos close to their
# original framing without much cropping.
TARGET_W = 1200
TARGET_RATIO = 4 / 3
JPEG_QUALITY = 82


def find_gutter(image):
    """
    Locate the near-white vertical band separating the two halves.

    Returns (start, end) columns, or None if the image doesn't look like a
    side-by-side pair.
    """
    grey = image.convert("L")
    width, height = grey.size
    pixels = grey.load()

    # Sample rows rather than every pixel — plenty accurate and much faster.
    rows = range(0, height, max(1, height // 60))

    def is_blank(x):
        return all(pixels[x, y] > 235 for y in rows)

    middle = width // 2
    search = range(int(width * 0.4), int(width * 0.6))
    blanks = [x for x in search if is_blank(x)]
    if not blanks:
        return None

    # Keep the run of blank columns closest to the centre.
    runs, run = [], [blanks[0]]
    for x in blanks[1:]:
        if x == run[-1] + 1:
            run.append(x)
        else:
            runs.append(run)
            run = [x]
    runs.append(run)
    best = min(runs, key=lambda r: abs((r[0] + r[-1]) / 2 - middle))
    return best[0], best[-1]


def trim_border(image, tolerance=235):
    """Shave off any solid near-white frame around the edges."""
    grey = image.convert("L")
    width, height = grey.size
    pixels = grey.load()
    cols = range(0, height, max(1, height // 40))
    rows = range(0, width, max(1, width // 40))

    left = 0
    while left < width - 1 and all(pixels[left, y] > tolerance for y in cols):
        left += 1
    right = width - 1
    while right > left + 1 and all(pixels[right, y] > tolerance for y in cols):
        right -= 1
    top = 0
    while top < height - 1 and all(pixels[x, top] > tolerance for x in rows):
        top += 1
    bottom = height - 1
    while bottom > top + 1 and all(pixels[x, bottom] > tolerance for x in rows):
        bottom -= 1

    return image.crop((left, top, right + 1, bottom + 1))


def to_target(image):
    """Centre-crop to 4:3, resize, and drop the alpha channel for JPEG."""
    width, height = image.size
    if width / height > TARGET_RATIO:
        new_w = int(height * TARGET_RATIO)
        offset = (width - new_w) // 2
        image = image.crop((offset, 0, offset + new_w, height))
    else:
        new_h = int(width / TARGET_RATIO)
        offset = (height - new_h) // 2
        image = image.crop((0, offset, width, offset + new_h))

    image = image.resize((TARGET_W, int(TARGET_W / TARGET_RATIO)), Image.LANCZOS)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def save(image, name):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.jpg"
    image.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    size_kb = path.stat().st_size / 1024
    print(f"  {path.relative_to(pathlib.Path.cwd())}  {image.size[0]}x{image.size[1]}  {size_kb:.0f} KB")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    source = pathlib.Path(sys.argv[1]).expanduser()
    slug = sys.argv[2]
    split = "--no-split" not in sys.argv

    try:
        # Read the bytes rather than handing Pillow a path: on a managed Mac
        # the sandbox can allow reads from ~/Desktop while blocking stat().
        original = Image.open(io.BytesIO(source.read_bytes()))
    except (OSError, PermissionError) as err:
        print(f"Can't read {source}: {err}")
        return 1

    print(f"{source.name}  {original.size[0]}x{original.size[1]}")

    if not split:
        save(to_target(trim_border(original)), slug)
        return 0

    gutter = find_gutter(original)
    if not gutter:
        print("  No centre gutter found — treating it as one photo.")
        save(to_target(trim_border(original)), slug)
        return 0

    start, end = gutter
    print(f"  Split at columns {start}-{end}")
    width, height = original.size
    before = original.crop((0, 0, start, height))
    after = original.crop((end + 1, 0, width, height))

    save(to_target(trim_border(before)), f"{slug}-before")
    save(to_target(trim_border(after)), f"{slug}-after")
    return 0


if __name__ == "__main__":
    sys.exit(main())
