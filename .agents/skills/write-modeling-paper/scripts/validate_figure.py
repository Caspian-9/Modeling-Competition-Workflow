from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


SUPPORTED_FORMATS = {".pdf", ".png", ".svg"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _issue(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _inspect_png(
    path: Path,
    *,
    minimum_width: int,
    minimum_height: int,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        return {}, [_issue("invalid_png", "error", "PNG signature or IHDR is invalid")]
    width, height = struct.unpack(">II", header[16:24])
    if width < minimum_width or height < minimum_height:
        issues.append(
            _issue(
                "small_raster",
                "error",
                f"raster dimensions {width}x{height} are below "
                f"{minimum_width}x{minimum_height}",
            )
        )

    possible_blank: bool | None = None
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as image:
            image.load()
            rgba = image.convert("RGBA")
            rgb_stats = ImageStat.Stat(rgba.convert("RGB"))
            alpha_extrema = rgba.getchannel("A").getextrema()
            rgb_extrema = rgba.convert("RGB").getextrema()
        possible_blank = max(rgb_stats.var) < 5.0 or all(
            low > 245 for low, _high in rgb_extrema
        )
        if alpha_extrema[1] < 5:
            possible_blank = True
        if possible_blank:
            issues.append(
                _issue("possible_blank", "error", "PNG is blank or nearly blank")
            )
    except ImportError:
        issues.append(
            _issue(
                "pixel_check_unavailable",
                "warning",
                "Pillow is unavailable; pixel-level blank detection was skipped",
            )
        )
    except OSError as error:
        issues.append(_issue("unreadable_png", "error", str(error)))

    return {
        "width": width,
        "height": height,
        "possible_blank": possible_blank,
    }, issues


def _inspect_svg(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        return {}, [_issue("invalid_svg", "error", str(error))]
    if not root.tag.lower().endswith("svg"):
        return {}, [_issue("invalid_svg_root", "error", "root element is not svg")]
    return {
        "width": root.attrib.get("width"),
        "height": root.attrib.get("height"),
        "view_box": root.attrib.get("viewBox"),
    }, []


def _inspect_pdf(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    with path.open("rb") as handle:
        header = handle.read(5)
        handle.seek(max(0, path.stat().st_size - 1024))
        trailer = handle.read()
    issues: list[dict[str, str]] = []
    if header != b"%PDF-":
        issues.append(_issue("invalid_pdf_header", "error", "PDF header is invalid"))
    if b"%%EOF" not in trailer:
        issues.append(_issue("missing_pdf_eof", "error", "PDF EOF marker is missing"))
    return {}, issues


def validate_figure(
    file_path: str | Path,
    output_root: str | Path,
    *,
    minimum_bytes: int = 512,
    minimum_width: int = 900,
    minimum_height: int = 600,
) -> dict[str, Any]:
    path = Path(file_path).resolve()
    root = Path(output_root).resolve()
    issues: list[dict[str, str]] = []
    details: dict[str, Any] = {}

    if not _inside(path, root):
        issues.append(_issue("outside_output_root", "error", str(path)))
    if path.is_symlink():
        issues.append(_issue("symlink_output", "error", "symlink outputs are forbidden"))
    if not path.is_file():
        issues.append(_issue("missing_output", "error", "figure file does not exist"))
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        issues.append(_issue("unsupported_format", "error", suffix or "no extension"))

    size = path.stat().st_size if path.is_file() else 0
    if path.is_file() and size < minimum_bytes:
        issues.append(
            _issue(
                "tiny_output",
                "error",
                f"file size {size} bytes is below {minimum_bytes}",
            )
        )

    if path.is_file() and suffix in SUPPORTED_FORMATS:
        if suffix == ".png":
            details, format_issues = _inspect_png(
                path,
                minimum_width=minimum_width,
                minimum_height=minimum_height,
            )
        elif suffix == ".svg":
            details, format_issues = _inspect_svg(path)
        else:
            details, format_issues = _inspect_pdf(path)
        issues.extend(format_issues)

    failed = any(item["severity"] == "error" for item in issues)
    return {
        "schema_version": "1.0",
        "status": "FAIL" if failed else "PASS",
        "file": path.as_posix(),
        "output_root": root.as_posix(),
        "format": suffix.lstrip("."),
        "size_bytes": size,
        "output_sha256": _digest(path) if path.is_file() else None,
        "details": details,
        "issues": issues,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a generated paper figure")
    parser.add_argument("--file", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--minimum-bytes", type=int, default=512)
    parser.add_argument("--minimum-width", type=int, default=900)
    parser.add_argument("--minimum-height", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report_path = Path(args.report).resolve()
    output_root = Path(args.output_root).resolve()
    if not _inside(report_path, output_root):
        print("report path must stay inside output root", file=sys.stderr)
        return 2
    report = validate_figure(
        args.file,
        output_root,
        minimum_bytes=args.minimum_bytes,
        minimum_width=args.minimum_width,
        minimum_height=args.minimum_height,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "report": report_path.as_posix()}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
