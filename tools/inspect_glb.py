#!/usr/bin/env python3
"""Inspect GLB 2.0 structure and extract embedded PNG/JPEG images.

Usage:
    python inspect_glb.py ../bmw-x5.glb --out ../../build

This is an analysis helper; it does not convert GLB into a MudRunner game mesh.
"""
import argparse
import json
import struct
from pathlib import Path


def load_glb(path: Path):
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("Not a binary glTF (GLB) file")
    version, declared_length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ValueError(f"Expected GLB 2.0, got version {version}")

    offset = 12
    document = None
    binary = b""
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
        elif chunk_type == 0x004E4942:
            binary = chunk

    if document is None:
        raise ValueError("GLB JSON chunk is missing")
    if declared_length > len(data):
        raise ValueError("GLB header length exceeds actual file size")
    return document, binary


def safe_name(value):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("glb", type=Path)
    parser.add_argument("--out", type=Path, default=Path("build"))
    args = parser.parse_args()

    doc, binary = load_glb(args.glb)
    out = args.out
    texture_dir = out / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)

    views = doc.get("bufferViews", [])
    images = []
    for index, image in enumerate(doc.get("images", [])):
        name = image.get("name") or f"image_{index}"
        if "uri" in image:
            images.append({"index": index, "name": name, "uri": image["uri"]})
            continue
        view_index = image.get("bufferView")
        if view_index is None or view_index >= len(views):
            images.append({"index": index, "name": name, "error": "missing bufferView"})
            continue
        view = views[view_index]
        start = view.get("byteOffset", 0)
        end = start + view["byteLength"]
        mime = image.get("mimeType", "application/octet-stream")
        extension = {"image/png": ".png", "image/jpeg": ".jpg"}.get(mime, ".bin")
        target = texture_dir / f"{index:02d}_{safe_name(name)}{extension}"
        target.write_bytes(binary[start:end])
        images.append({
            "index": index, "name": name, "mimeType": mime,
            "file": target.as_posix(), "bytes": end - start
        })

    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    materials = doc.get("materials", [])
    report = {
        "source": args.glb.name,
        "asset": doc.get("asset", {}),
        "counts": {
            "nodes": len(nodes),
            "meshes": len(meshes),
            "materials": len(materials),
            "images": len(doc.get("images", []))
        },
        "nodes": [
            {
                "index": i,
                "name": node.get("name", f"node_{i}"),
                "mesh": node.get("mesh"),
                "children": node.get("children", []),
                "translation": node.get("translation"),
                "rotation": node.get("rotation"),
                "scale": node.get("scale")
            }
            for i, node in enumerate(nodes)
        ],
        "meshes": [
            {"index": i, "name": mesh.get("name", f"mesh_{i}"),
             "primitive_count": len(mesh.get("primitives", []))}
            for i, mesh in enumerate(meshes)
        ],
        "materials": [
            {"index": i, "name": material.get("name", f"material_{i}"),
             "alphaMode": material.get("alphaMode", "OPAQUE")}
            for i, material in enumerate(materials)
        ],
        "images": images
    }

    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "model_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Nodes: {len(nodes)} | meshes: {len(meshes)} | materials: {len(materials)}")
    print(f"Report: {report_path}")
    print(f"Extracted textures: {texture_dir}")


if __name__ == "__main__":
    main()
