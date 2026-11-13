"""Offline publication checks. No network, USB, CAN, subprocess or hardware I/O."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/validation/release-manifest.json"
SKIP = {".git", "__pycache__", "node_modules", ".venv", "build", ".zig-cache", "managed_components"}
DENY_DIR = {".dev", "outputs", "packages"}
DENY_EXT = {".bin", ".elf", ".exe", ".dll", ".pdb", ".pem", ".key", ".jks", ".keystore", ".raw", ".log", ".zip", ".pyc"}
TEXT_EXT = {".py", ".cpp", ".hpp", ".h", ".c", ".cjs", ".js", ".css", ".json", ".md", ".html", ".csv", ".txt", ".ps1", ".sh", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".cmake", ".defaults", ".projbuild", ".inc", ".urdf", ".gitattributes", ".gitignore"}
TOKEN = re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
USER_PATH = re.compile(r"(?i)[A-Z]:(?:\\\\|\\|/)+Users(?:\\\\|\\|/)+(?!USER(?:[\\/]|\b)|Public(?:[\\/]|\b)|Default(?:[\\/]|\b))[^\\/\s\"']+")
URL_PASSWORD = re.compile(r"https?://[^\s/:@]+:[^\s/@]+@", re.I)
CLOUD_RESOURCE = re.compile(r"https?://(?:(?:drive|docs)\.google\.com/(?:drive/(?:u/\d+/)?folders/|file/d/|document/d/|spreadsheets/d/|presentation/d/|open\?id=)[A-Za-z0-9_-]{8,}|[A-Za-z0-9.-]+\.atlassian\.net/(?:wiki/[^\s<>\"']*\d{5,}|browse/[A-Z]+-\d+)|www\.googleapis\.com/drive/v3/files/[A-Za-z0-9_-]{8,})", re.I)
SITE_TAILNET = re.compile(r"(?<![\w.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+(?![\w.])")
REVIEWED_IMAGES = {"docs/brand/kmjh-01-identity.webp": "a2a4c35a7f7299aa861754dde8b7afb07dcbbbc0daedead379d2a4267eae7d55"}


def files():
    for directory, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for d in dirs:
            if (Path(directory) / d).is_symlink():
                raise ValueError("Symlink directory is not a public asset")
        for name in sorted(names):
            p = Path(directory) / name
            rel = p.relative_to(ROOT).as_posix()
            if rel != MANIFEST:
                yield p, rel


def inspect():
    entries = []
    counts = {"python": 0, "json": 0, "xml": 0, "stl": 0, "webp": 0}
    for p, rel in files():
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Outside/symlink asset: " + rel)
        if DENY_DIR.intersection(p.relative_to(ROOT).parts) or p.suffix.lower() in DENY_EXT:
            raise ValueError("Private/generated artifact is not publishable: " + rel)
        if (p.name.startswith(".env") and p.name != ".env.example") or p.name == "credentials.json" or p.name.startswith("secrets."):
            raise ValueError("Credential filename: " + rel)
        if p.name.upper() == "GOOGLE_DRIVE_ARCHIVE.JSON":
            raise ValueError("Internal cloud inventory is not a public source document: " + rel)
        raw = p.read_bytes()
        if len(raw) > 50 * 1024 * 1024:
            raise ValueError("File exceeds public limit: " + rel)
        if p.suffix.lower() == ".stl":
            if not rel.startswith("models/robot-arm-urdf-v4/") or len(raw) < 84 or len(raw) != 84 + int.from_bytes(raw[80:84], "little") * 50:
                raise ValueError("Unexpected or malformed STL: " + rel)
            if re.search(rb"(?:[A-Z]:[\\/]|@|https?://|PRIVATE KEY)", raw[:80], re.I):
                raise ValueError("STL metadata requires review: " + rel)
            counts["stl"] += 1
        elif p.suffix.lower() == ".webp":
            if REVIEWED_IMAGES.get(rel) != hashlib.sha256(raw).hexdigest() or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP" or any(m in raw for m in (b"EXIF", b"XMP ")):
                raise ValueError("Unexpected image/metadata: " + rel)
            counts["webp"] += 1
        else:
            if p.suffix.lower() not in TEXT_EXT and p.name not in {".gitignore", ".gitattributes", "CMakeLists.txt", "Kconfig", "Makefile"}:
                raise ValueError("Unknown public file type: " + rel)
            text = raw.decode("utf-8-sig")
            if TOKEN.search(text) or USER_PATH.search(text) or URL_PASSWORD.search(text):
                raise ValueError("Credential/personal-path pattern: " + rel)
            if CLOUD_RESOURCE.search(text) or SITE_TAILNET.search(text):
                raise ValueError("Private cloud resource or site tailnet address: " + rel)
            if p.suffix == ".py":
                ast.parse(text, filename=rel)
                counts["python"] += 1
            elif p.suffix == ".json":
                json.loads(text)
                counts["json"] += 1
            elif p.suffix == ".urdf":
                ET.fromstring(text)
                counts["xml"] += 1
        entries.append({"path": rel, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    urdf = ROOT / "models/robot-arm-urdf-v4/robot_arm.urdf"
    tree = ET.fromstring(urdf.read_bytes())
    for mesh in tree.iter("mesh"):
        filename = mesh.attrib["filename"]
        target = (urdf.parent / filename).resolve()
        if not filename.startswith("meshes/") or not target.is_relative_to(urdf.parent.resolve()) or not target.is_file():
            raise ValueError("Missing/unsafe v4 mesh reference")
    return sorted(entries, key=lambda x: x["path"]), counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    entries, counts = inspect()
    manifest = ROOT / MANIFEST
    if args.write_manifest:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"schema": 1, "scope": "Public files except this manifest and ignored build/dependency caches", "files": entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    expected = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    if entries != expected:
        raise ValueError("Public tree differs from manifest; review changes before --write-manifest")
    print(json.dumps({"status": "PASS", "files": len(entries), "bytes": sum(e["bytes"] for e in entries), "syntax_and_asset_checks": counts, "hardware_access": False}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError, SyntaxError, ET.ParseError) as error:
        print("PUBLICATION CHECK FAILED: " + str(error), file=sys.stderr)
        raise SystemExit(1) from error
