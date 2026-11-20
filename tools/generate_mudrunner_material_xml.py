#!/usr/bin/env python3
"""Generate deduplicated MudRunner CombineXMesh material XML and TGA maps from GLB."""
import hashlib
import io
import json
import re
import struct
from collections import Counter
from html import escape
from pathlib import Path

from PIL import Image, ImageChops

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
SNOWRUNNER_ATTRIBUTES = (
    "SoftForceScale", "RadiusOffset", "BodyFriction", "HardpointX",
    "HardpointDefaultY", "HardpointDefaultZ", "SuspensionMin",
    "SuspensionStrength",
)
GLASS_RE = re.compile(r"glass|window|windshield|windscreen|headlight|headlamp|lamp|lens", re.I)
CHROME_RE = re.compile(r"chrome|chrom|metal|metallic_trim|brightwork", re.I)
PAINT_RE = re.compile(r"paint|body|car[_ -]?color|exterior", re.I)


def read_glb(path):
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError("Source is not a binary GLB")
    version, total = struct.unpack_from("<II", data, 4)
    if version != 2 or total > len(data):
        raise RuntimeError("Unsupported or truncated GLB")
    offset = 12
    doc = binary = None
    while offset < total:
        if offset + 8 > total:
            raise RuntimeError("Truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + length]
        if len(chunk) != length:
            raise RuntimeError("Truncated GLB chunk")
        offset += length
        if kind == 0x4E4F534A:
            doc = json.loads(chunk.rstrip(b" \t\r\n\0").decode("utf-8"))
        elif kind == 0x004E4942:
            binary = chunk
    if doc is None:
        raise RuntimeError("GLB JSON chunk missing")
    return doc, binary or b""


def image_bytes(doc, binary, image):
    if "uri" in image:
        raise RuntimeError("External image URI is not supported: " + image["uri"])
    view = doc["bufferViews"][image["bufferView"]]
    start = view.get("byteOffset", 0)
    payload = binary[start:start + view["byteLength"]]
    if len(payload) != view["byteLength"]:
        raise RuntimeError("Truncated embedded GLB image")
    return payload


def safe_stem(value):
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", value).strip("._")
    stem = re.sub(r"_+", "_", stem)
    return (stem or "material") + "_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def material_index(doc):
    """Keep the first source material for each GLB name; duplicate names never overwrite it."""
    by_name = {}
    counts = Counter()
    for index, material in enumerate(doc.get("materials", [])):
        name = material.get("name") or ("Material_%03d" % index)
        counts[name] += 1
        by_name.setdefault(name, (index, material))
    duplicates = {name: count for name, count in counts.items() if count > 1}
    if duplicates:
        print("GLB_DUPLICATE_MATERIAL_NAMES_COLLAPSED", duplicates)
    return by_name


def matching_brace(source, opening):
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos
    raise RuntimeError("Unbalanced braces in DirectX .X file")


def x_material_parts(path):
    """Return (frame_name, part_index, material_name) from each direct mesh frame."""
    source = path.read_text(encoding="utf-8", errors="replace")
    result = []
    frame_matches = list(re.finditer(r"\bFrame\s+([^\s{]+)\s*\{", source))
    for frame_match in frame_matches:
        opening = frame_match.end() - 1
        closing = matching_brace(source, opening)
        frame_body = source[opening + 1:closing]
        nested = re.search(r"\bFrame\s+[^\s{]+\s*\{", frame_body)
        direct_body = frame_body[:nested.start()] if nested else frame_body
        mesh_match = re.search(r"\bMeshMaterialList\s*\{", direct_body)
        if not mesh_match:
            continue
        list_open = direct_body.find("{", mesh_match.start())
        list_close = matching_brace(direct_body, list_open)
        material_block = direct_body[list_open + 1:list_close]
        names = re.findall(r"\bMaterial\s+([^\s{]+)\s*\{", material_block)
        if not names:
            continue
        declared_count = re.match(r"\s*(\d+)\s*;", material_block)
        if declared_count and int(declared_count.group(1)) != len(names):
            raise RuntimeError(
                "%s: MeshMaterialList in frame %s declares %s materials but contains %s"
                % (path, frame_match.group(1), declared_count.group(1), len(names))
            )
        for part_index, name in enumerate(names):
            result.append((frame_match.group(1), part_index, name))
    if not result:
        raise RuntimeError("No frame/material assignments found in " + str(path))
    print("X_MATERIAL_PARTS", path, len(result))
    return result


def resolve_material(name, by_name):
    if name in by_name:
        return by_name[name][1]
    # Blender/OBJ importers append .001, .002, ... to duplicate datablock names.
    base = re.sub(r"\.\d{3,}$", "", name)
    if base in by_name:
        return by_name[base][1]
    raise RuntimeError("MaterialName not found in GLB: " + name)


def source_base_image(doc, binary, material):
    pbr = material.get("pbrMetallicRoughness", {})
    info = pbr.get("baseColorTexture")
    if info is None:
        return None
    texture = doc.get("textures", [])[info["index"]]
    image_index = texture.get("source")
    if image_index is None:
        image_index = texture.get("extensions", {}).get("KHR_texture_basisu", {}).get("source")
    if image_index is None:
        raise RuntimeError("GLB base-color texture has no image source")
    return Image.open(io.BytesIO(image_bytes(doc, binary, doc["images"][image_index]))).convert("RGBA")


def make_diffuse(doc, binary, name, material):
    pbr = material.get("pbrMetallicRoughness", {})
    factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
    factor = [max(0.0, min(1.0, float(v))) for v in factor]
    image = source_base_image(doc, binary, material)
    if image is None:
        rgba = tuple(round(v * 255) for v in factor)
        image = Image.new("RGBA", (32, 32), rgba)
    else:
        rgb = Image.merge("RGB", image.split()[:3])
        tint = Image.new("RGB", image.size, tuple(round(v * 255) for v in factor[:3]))
        rgb = ImageChops.multiply(rgb, tint)
        image = Image.merge("RGBA", (*rgb.split(), image.getchannel("A")) )

    semantic_name = material.get("name") or name
    is_glass = bool(GLASS_RE.search(semantic_name))
    if is_glass:
        # A true 32-bit TGA with constant 40% opacity for MudRunner alpha blending.
        image.putalpha(Image.new("L", image.size, 102))
    else:
        # Preserve the source alpha channel and the GLB baseColorFactor alpha.
        alpha = image.getchannel("A").point(lambda a: round(a * factor[3]))
        image.putalpha(alpha)

    filename = "m_%s_d.tga" % safe_stem(name)
    target = TEXTURES / filename
    image.save(target, format="TGA")
    with Image.open(target) as check:
        if check.mode != "RGBA":
            raise RuntimeError("Diffuse TGA must be 32-bit RGBA: " + filename)
    return filename, is_glass


def make_specular(name, material, semantic_name=None):
    semantic_name = semantic_name or name
    pbr = material.get("pbrMetallicRoughness", {})
    metallic = float(pbr.get("metallicFactor", 1.0 if CHROME_RE.search(semantic_name) else 0.0))
    roughness = float(pbr.get("roughnessFactor", 0.25 if (CHROME_RE.search(semantic_name) or PAINT_RE.search(semantic_name)) else 0.7))
    if GLASS_RE.search(semantic_name):
        level = 220
    elif CHROME_RE.search(semantic_name):
        level = 248
    elif PAINT_RE.search(semantic_name):
        level = 220
    else:
        level = round(80 + 150 * max(0.0, min(1.0, metallic)) * (1.0 - 0.35 * max(0.0, min(1.0, roughness))))
    filename = "m_%s_s.tga" % safe_stem(name)
    target = TEXTURES / filename
    Image.new("RGB", (32, 32), (level, level, level)).save(target, format="TGA")
    return filename


def strip_snowrunner_attributes(xml_text):
    for attr in SNOWRUNNER_ATTRIBUTES:
        xml_text = re.sub(r"\s+" + re.escape(attr) + r'\s*=\s*"[^"]*"', "", xml_text)
    return xml_text


def make_xml(x_path, xml_path, doc, binary, by_name):
    assignments = x_material_parts(x_path)
    # One XML Material can target multiple mesh parts. This prevents each
    # material from becoming a repeated default material in MudRunner Editor.
    grouped = {}
    for frame_name, part_index, x_name in assignments:
        grouped.setdefault(x_name, []).append("%s %d" % (frame_name, part_index))

    rows = ['<?xml version="1.0" encoding="utf-8"?>', "<CombineXMesh>"]
    for x_name, mesh_parts in grouped.items():
        material = resolve_material(x_name, by_name)
        diffuse, is_glass = make_diffuse(doc, binary, x_name, material)
        semantic_name = material.get("name") or x_name
        specular = make_specular(x_name, material, semantic_name)
        attrs = [
            'MeshParts="%s"' % escape(", ".join(mesh_parts), quote=True),
            'DiffuseMap="%s"' % diffuse,
            'SpecularMap="%s"' % specular,
        ]
        if is_glass:
            attrs.append('Blending="alpha"')
        rows.append("  <Material " + " ".join(attrs) + " />")

    rows.append("</CombineXMesh>")
    xml_text = strip_snowrunner_attributes("\n".join(rows) + "\n")
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(xml_text, encoding="utf-8")

    meshparts = re.findall(r'<Material\s+MeshParts="([^"]+)"', xml_text)
    if len(meshparts) != len(grouped):
        raise RuntimeError("Material MeshParts assignments missing or duplicated in " + str(xml_path))
    covered = [part.strip() for value in meshparts for part in value.split(",")]
    expected = ["%s %d" % (frame, index) for frame, index, _name in assignments]
    if Counter(covered) != Counter(expected):
        raise RuntimeError("MeshParts coverage mismatch in " + str(xml_path))
    for attr in SNOWRUNNER_ATTRIBUTES:
        if re.search(r"\b" + re.escape(attr) + r"\s*=", xml_text):
            raise RuntimeError("SnowRunner-only attribute survived XML generation: " + attr)
    for rel in re.findall(r'(?:DiffuseMap|SpecularMap)="([^"]+)"', xml_text):
        if Path(rel).name != rel or not (TEXTURES / rel).is_file():
            raise RuntimeError("XML references missing texture: " + rel)
    glass_count = sum(bool(GLASS_RE.search(resolve_material(name, by_name).get("name") or name))
                      for name in grouped)
    print("GENERATED", xml_path, "materials=", len(grouped), "meshparts=", len(covered), "glass=", glass_count)


def main():
    doc, binary = read_glb(GLB)
    TEXTURES.mkdir(parents=True, exist_ok=True)
    by_name = material_index(doc)
    make_xml(BODY_X, BODY_XML, doc, binary, by_name)
    for xml, xfile in WHEEL_FILES.items():
        make_xml(xfile, ROOT / xml, doc, binary, by_name)
    print("MATERIAL_XML_GENERATION_OK")


if __name__ == "__main__":
    main()
