from __future__ import annotations

import argparse
import colorsys
import re
import uuid
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageStat


README_NAME = "README.md"
DEFAULT_RAW_BASE_URL = "https://raw.githubusercontent.com/touchnggrass/src/main/img"
UUID_HEX_PATTERN = re.compile(r"[0-9a-fA-F]{32}")
SCRIPT_PATH = Path(__file__).resolve()


def has_uuid_name(path: Path) -> bool:
    return UUID_HEX_PATTERN.fullmatch(path.stem) is not None


def image_color_sort_key(path: Path) -> tuple[float, float, float]:
    try:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            mean_values = ImageStat.Stat(rgb_image).mean
    except (OSError, ValueError):
        return (0.0, 0.0, 0.0)

    if not mean_values:
        return (0.0, 0.0, 0.0)

    average_r, average_g, average_b = (float(channel) for channel in mean_values[:3])
    hue, saturation, value = colorsys.rgb_to_hsv(
        average_r / 255,
        average_g / 255,
        average_b / 255,
    )
    return (hue, saturation, value)


def rename_files(directory: Path, raw_base_url: str, dry_run: bool = False) -> None:
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.name != README_NAME
        and path.resolve() != SCRIPT_PATH
    )
    used_names = {path.name for path in files}
    renames = []
    for path in files:
        if has_uuid_name(path):
            renames.append((path, path))
            continue
        destination = path.with_name(f"{uuid.uuid4().hex}{path.suffix}")
        while destination.name in used_names:
            destination = path.with_name(f"{uuid.uuid4().hex}{path.suffix}")
        used_names.add(destination.name)
        renames.append((path, destination))

    renames = sorted(renames, key=lambda item: image_color_sort_key(item[0]))

    for source, destination in renames:
        if source != destination:
            print(f"{source.name} -> {destination.name}")

    if dry_run:
        return

    temporary_renames = [
        (source, source.with_name(f".{uuid.uuid4().hex}.rename"))
        for source, destination in renames
        if source != destination
    ]
    for source, temporary in temporary_renames:
        source.rename(temporary)
    destinations = [destination for source, destination in renames if source != destination]
    for destination, (_, temporary) in zip(destinations, temporary_renames):
        temporary.rename(destination)

    image_gallery = [
        '<div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">',
    ]
    for _, destination in renames:
        link = f"{raw_base_url.rstrip('/')}/{quote(destination.name)}"
        image_gallery.append(
            f'<img src="{link}" alt="{destination.name}" '
            f'style="height: 200px; width: auto; display: block; border-radius: 8px;">'
        )
    image_gallery.append("</div>")
    root_readme = directory.parent / README_NAME
    root_readme.write_text("# src\n\n" + "\n".join(image_gallery) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rename files to UUID4 hex names and create an image README."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("img"),  
        help="Directory containing files to rename (default: img).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed names without renaming files.",
    )
    parser.add_argument(
        "--raw-base-url",
        default=DEFAULT_RAW_BASE_URL,
        help="Base URL used for image links in the generated README.",
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        parser.error(f"directory does not exist: {args.directory}")
    rename_files(args.directory, args.raw_base_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()