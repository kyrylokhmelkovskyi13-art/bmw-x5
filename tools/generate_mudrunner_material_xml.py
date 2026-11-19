#!/usr/bin/env python3
"""Generate MudRunner CombineXMesh material XML and TGA textures from the source GLB."""
# Executed by the release workflow after all five DirectX .X files are exported.
import io
import json
import re
import struct
from pathlib import Path
from PIL import Image

ROOT = Path(".")
GLB = ROOT / "bmw-x5.glb"
EXPORT = ROOT / "build/export"
TEXTURES = ROOT / "build/release/textures"
BODY_X = EXPORT / "bmw_x5.x"
WHEEL_FILES = {
    "meshes/wheels/bmw_x5_end_a_side_a.xml": EXPORT / "wheels/wheel_a_side_a.x",
    "meshes/wheels/bmw_x5_end_a_side_b.xml": EXPORT / "wheels/wheel_a_side_b.x",
    "meshes/wheels/bmw_x5_end_b_side_a.xml": EXPORT / "wheels/wheel_b_side_a.x",
    "meshes/wheels/bmw_x5_end_b_side_b.xml": EXPORT / "wheels/wheel_b_side_b.x",
}
BODY_XML = ROOT / "meshes/trucks/bmw_x5.xml"

def read_glb(path):
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError("Source is not a binary GLB")
    version, total = struct.unpack_from('<II', data, 4)
    if version != 2 or total > len(data):
        raise RuntimeError("Unsupported or truncated GLB")
    offset = 12
    doc = binary = None
    while offset < total:
        length, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        chunk = data[offset:offset + length]
        offset += length
        if kind == 0x4E4F534A:
            doc = json.loads(chunk.rstrip().decode("utf-8"))
        elif kind == 0x004E4942:
            binary = chunk
    if doc is None:
        raise RuntimeError("GLB JSON chunk missing")
    return doc, binary or b''

def image_bytes(doc, binary, image):
    if "uri" in image:
        raise RuntimeError("External image URI is not supported in embedded GLB: " + image["uri"])
    view = doc["bufferViews"][image["bufferView"]]
    start = view.get("byteOffset", 0)
    return binary[start:start + view["byteLength"]]

def main():
    doc, binary = read_glb(GLB)
    TEXTURES.mkdir(parents=True, exist_ok=True)
    image_paths = {}
    for i, item in enumerate(doc.get("images", [])):
        payload = image_bytes(doc, binary, item)
        im = Image.open(io.BytesIO(payload)).convert('RGBA')
        target = TEXTURES / ("gltf_embedded_%d.tga" % i)
        im.save(target, format='TGA')
        image_paths[i] = target.name

    materials = {}
    for material in doc.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
        texture_info = pbr.get("baseColorTexture")
        image_index = None
        if texture_info is not None:
            texture = doc["textures"][texture_info["index"]]
            image_index = texture.get("source")
        materials[material.get("name", "Material")] = {"factor": factor, "image": image_index}

    def x_materials(path):
        source = path.read_text(encoding='utf-8', errors='replace')
        names = re.findall(r"\bMaterial\s+([^\s{]+)\s*\{", source)
        return list(dict.fromkeys(names))

    def make_xml(x_path, xml_path):
        names = x_materials(x_path)
        if not names:
            raise RuntimeError("No Material declarations found in " + str(x_path))
        rows = ['<?xml version="1.0" encoding="utf-8"?>', '<CombineXMesh>']
        for name in names:
            entry = materials.get(name)
            if entry is None:
                raise RuntimeError("MaterialName not found in GLB: " + name)
            image_index = entry['image']
            if image_index is not None:
                if image_index not in image_paths:
                    raise RuntimeError("GLB texture source index missing: %s (%s)" % (image_index, name))
                diffuse = image_paths[image_index]
            else:
                rgba = entry['factor']
                color = tuple(max(0, min(255, round(float(v) * 255))) for v in rgba)
                safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
                # MudRunner treats "__" as a semantic texture-postfix marker.
                # Collapse repeated underscores before creating the filename.
                safe_name = re.sub(r"_{2,}", "_", safe_name)
                target = TEXTURES / ("solid_" + safe_name + ".tga")
                Image.new('RGBA', (16, 16), color).save(target, format='TGA')
                diffuse = target.name
            if "__" in Path(diffuse).name:
                raise RuntimeError("Invalid MudRunner texture filename contains '__': " + diffuse)
            escaped_name = name.replace("&", "&amp;").replace(chr(34), "&quot;")
            rows.append('  <Material Name="%s" DiffuseMap="%s" />' % (escaped_name, diffuse))
        if len(names) != len(set(names)):
            raise RuntimeError("Duplicate material names found in " + str(x_path))
        rows.append('</CombineXMesh>')
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        xml_path.write_text('\n'.join(rows) + '\n', encoding='utf-8')
        generated_names = re.findall(r'<Material\\s+Name="([^"]+)"', xml_path.read_text(encoding='utf-8'))
        if len(generated_names) != len(set(generated_names)):
            raise RuntimeError("Duplicate <Material> entries generated in " + str(xml_path))
        print("GENERATED", xml_path, "materials=", len(generated_names))

    make_xml(BODY_X, BODY_XML)
    for xml, xfile in WHEEL_FILES.items():
        make_xml(xfile, ROOT / xml)

    for xml in [BODY_XML] + [ROOT / p for p in WHEEL_FILES]:
        for rel in re.findall(r'DiffuseMap="([^"]+)"', xml.read_text(encoding='utf-8')):
            if Path(rel).name != rel or not (TEXTURES / rel).is_file():
                raise RuntimeError("XML references missing texture: " + rel)
    print("MATERIAL_XML_GENERATION_OK")

if __name__ == '__main__':
    main()
