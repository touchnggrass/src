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
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
SCRIPT_PATH = Path(__file__).resolve()
FOLDER_ORDER = [
    "wallpapers", 
    "art",
]


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


def image_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.name != README_NAME
        and path.resolve() != SCRIPT_PATH
    )


def rename_files_in_directory(directory: Path) -> list[tuple[Path, Path]]:
    files = image_files(directory)
    used_names = {path.name for path in files}
    renames = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".jpeg":
            destination_suffix = ".jpg"
        elif suffix in SUPPORTED_IMAGE_SUFFIXES:
            destination_suffix = suffix
        else:
            destination_suffix = ".png"
        if has_uuid_name(path) and destination_suffix == path.suffix:
            renames.append((path, path))
            continue
        destination = path.with_name(f"{uuid.uuid4().hex}{destination_suffix}")
        while destination.name in used_names:
            destination = path.with_name(f"{uuid.uuid4().hex}{destination_suffix}")
        used_names.add(destination.name)
        renames.append((path, destination))

    return sorted(renames, key=lambda item: image_color_sort_key(item[0]))


def rename_files(directory: Path, raw_base_url: str, dry_run: bool = False) -> None:
    folders = {path.name: path for path in directory.iterdir() if path.is_dir()}
    ordered_folders = [folders[name] for name in FOLDER_ORDER if name in folders]
    ordered_folders.extend(
        path for name, path in sorted(folders.items()) if name not in FOLDER_ORDER
    )
    directories = [directory, *ordered_folders]
    directory_renames = [
        (current_directory, rename_files_in_directory(current_directory))
        for current_directory in directories
    ]
    renames = [rename for _, current_renames in directory_renames for rename in current_renames]

    for source, destination in renames:
        if source != destination:
            print(f"{source.name} -> {destination.name}")

    if dry_run:
        return

    for _, current_renames in directory_renames:
        temporary_renames = [
            (source, source.with_name(f".{uuid.uuid4().hex}.rename"))
            for source, destination in current_renames
            if source != destination
        ]
        for source, temporary in temporary_renames:
            source.rename(temporary)
        destinations = [destination for source, destination in current_renames if source != destination]
        for destination, (_, temporary) in zip(destinations, temporary_renames):
            if destination.suffix == ".png" and temporary.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                with Image.open(temporary) as image:
                    image.save(destination, format="PNG")
                temporary.unlink()
            else:
                temporary.rename(destination)

    readme_sections = ["# src"]
    for current_directory, current_renames in directory_renames:
        if current_directory != directory:
            readme_sections.append(f"## `{current_directory.name}`")
        if not current_renames:
            continue
        image_gallery = [
            '<div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">',
        ]
        relative_directory = current_directory.relative_to(directory)
        for _, destination in current_renames:
            relative_path = relative_directory / destination.name
            link = f"{raw_base_url.rstrip('/')}/{quote(str(relative_path), safe='/')}"
            image_gallery.append(
                f'<img src="{link}" alt="{destination.name}" '
                f'style="height: 200px; width: auto; display: block; border-radius: 8px;">'
            )
        image_gallery.append("</div>")
        readme_sections.append("\n".join(image_gallery))

    root_readme = directory.parent / README_NAME
    root_readme.write_text("\n\n".join(readme_sections) + "\n")


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