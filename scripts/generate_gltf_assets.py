"""Generate genuine .gltf asset models for the GridMind 3D digital twin.

Creates embedded-binary glTF files (JSON + base64 buffer) for the physical
assets rendered in the volumetric particle-flow scene:

* ``solar_array.gltf``    — tilted panel bank on a frame
* ``battery_bank.gltf``  — stacked battery cabinet modules
* ``wind_turbine.gltf``  — hub + tower (rotor animated in code)
* ``ev_charger.gltf``    — charging post
* ``hospital.gltf``      — critical facility block

Run from the project root:
    python scripts/generate_gltf_assets.py
"""

import base64
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "frontend" / "public" / "models"

# glTF accessor component types
FLOAT = 5126
UNSIGNED_SHORT = 5123


def _buffer_bytes(bin_chunks: list[bytes]) -> tuple[bytes, list[dict]]:
    """Concatenate chunks with 4-byte alignment; return buffer + accessors."""
    buffer = bytearray()
    accessors = []
    view_index = 0
    for chunk in bin_chunks:
        # pad to 4-byte alignment
        while len(buffer) % 4:
            buffer += b"\x00"
        accessors.append(
            {
                "bufferView": view_index,
                "componentType": FLOAT,
                "count": len(chunk) // 4,
                "type": "VEC3",
            }
        )
        view_index += 1
        buffer += chunk
    return bytes(buffer), accessors


def _mesh(name: str, primitives: list[dict]) -> dict:
    return {"name": name, "primitives": primitives}


def _positions_flat(tris: list[tuple[float, float, float]]) -> bytes:
    out = bytearray()
    for v in tris:
        for comp in v:
            out += struct.pack("<f", comp)
    return bytes(out)


def _indices_flat(idx: list[int]) -> bytes:
    return b"".join(struct.pack("<H", i) for i in idx)


def box_vertices(cx, cy, cz, sx, sy, sz):
    """Return the 8 corner positions of an axis-aligned box."""
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    return [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]


BOX_FACES = [
    (0, 1, 2), (0, 2, 3),  # front  (-z)
    (4, 6, 5), (4, 7, 6),  # back   (+z)
    (0, 3, 7), (0, 7, 4),  # left   (-x)
    (1, 5, 6), (1, 6, 2),  # right  (+x)
    (3, 2, 6), (3, 6, 7),  # top    (+y)
    (0, 4, 5), (0, 5, 1),  # bottom (-y)
]


def _box_chunk(cx, cy, cz, sx, sy, sz):
    verts = box_vertices(cx, cy, cz, sx, sy, sz)
    pos = []
    idx = []
    for face in BOX_FACES:
        base = len(pos)
        for fi in face:
            pos.append(verts[fi])
        idx.extend([base, base + 1, base + 2])
    return pos, idx


def _cylinder_chunks(cx, cy, cz, radius, height, segments=16):
    """Side + cap triangles for a vertical cylinder centred at (cx, cy, cz)."""
    pos = []
    idx = []

    def ring(y):
        pts = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            pts.append((cx + radius * math.cos(a), y, cz + radius * math.sin(a)))
        return pts

    bottom = ring(cy - height / 2)
    top = ring(cy + height / 2)
    for i in range(segments):
        j = (i + 1) % segments
        b0, b1 = len(pos) + i, len(pos) + j
        pos.append(bottom[i])
    base_bottom = 0
    top_start = len(pos)
    for p in top:
        pos.append(p)
    for i in range(segments):
        j = (i + 1) % segments
        idx.extend([top_start + i, base_bottom + i, base_bottom + j])
        idx.extend([top_start + i, base_bottom + j, top_start + j])
    # caps
    center_bottom = len(pos)
    pos.append((cx, cy - height / 2, cz))
    center_top = len(pos)
    pos.append((cx, cy + height / 2, cz))
    for i in range(segments):
        j = (i + 1) % segments
        idx.extend([center_bottom, base_bottom + j, base_bottom + i])
        idx.extend([center_top, top_start + i, top_start + j])
    return pos, idx


def build_gltf(parts: list[tuple[str, list, list, dict]], out_path: Path):
    """Assemble a glTF document from (name, positions, indices, material)."""
    bin_chunks = []
    for _, pos, idx, _mat in parts:
        bin_chunks.append(_positions_flat(pos))
        bin_chunks.append(_indices_flat(idx))

    buffer, pos_accessors = _buffer_bytes(bin_chunks)

    # Build buffer views: interleave position and index views
    views = []
    offset = 0
    pos_acc_list = []
    idx_acc_list = []
    acc_i = 0
    for _, pos, idx, _mat in parts:
        while offset % 4:
            buffer = bytearray(buffer)
            buffer += b"\x00"
            buffer = bytes(buffer)
            offset += 1
        pos_len = len(_positions_flat(pos))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": pos_len})
        pos_acc_list.append(
            {
                "bufferView": len(views) - 1,
                "componentType": FLOAT,
                "count": len(pos),
                "type": "VEC3",
                "min": [
                    min(v[i] for v in pos) for i in range(3)
                ],
                "max": [
                    max(v[i] for v in pos) for i in range(3)
                ],
            }
        )
        offset += pos_len

        while offset % 4:
            buffer = bytearray(buffer)
            buffer += b"\x00"
            buffer = bytes(buffer)
            offset += 1
        idx_len = len(_indices_flat(idx))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": idx_len})
        idx_acc_list.append(
            {
                "bufferView": len(views) - 1,
                "componentType": UNSIGNED_SHORT,
                "count": len(idx),
                "type": "SCALAR",
            }
        )
        offset += idx_len

    accessors = pos_acc_list + idx_acc_list

    materials = []
    meshes = []
    nodes = []
    n_pos = 0
    n_idx = 0
    for part_i, (name, pos, idx, mat) in enumerate(parts):
        material_idx = len(materials)
        materials.append(
            {
                "name": mat["name"],
                "pbrMetallicRoughness": {
                    "baseColorFactor": mat.get(
                        "color", [0.8, 0.8, 0.8, 1.0]
                    ),
                    "metallicFactor": mat.get("metallic", 0.1),
                    "roughnessFactor": mat.get("roughness", 0.7),
                },
            }
        )
        mesh = {
            "name": name,
            "primitives": [
                {
                    "attributes": {"POSITION": n_pos},
                    "indices": len(pos_acc_list) + n_idx,
                    "material": material_idx,
                    "mode": 4,
                }
            ],
        }
        meshes.append(mesh)
        nodes.append({"mesh": part_i, "name": name})
        n_pos += 1
        n_idx += 1

    doc = {
        "asset": {"version": "2.0", "generator": "GridMind asset builder"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [
            {
                "byteLength": len(buffer),
                "uri": "data:application/octet-stream;base64,"
                + base64.b64encode(buffer).decode("ascii"),
            }
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc), encoding="utf-8")
    print(f"  {out_path.name}: {len(buffer)} bytes geometry, {len(parts)} part(s)")


def solar_array():
    """Tilted panel bank: 3 rows × 4 columns of panels on a frame."""
    parts = []
    panel_mat = {"name": "panel_dark", "color": [0.05, 0.08, 0.14, 1.0], "metallic": 0.4, "roughness": 0.35}
    frame_mat = {"name": "frame_grey", "color": [0.65, 0.68, 0.72, 1.0]}

    tilt = math.radians(25)
    for row in range(3):
        for col in range(4):
            cx = (col - 1.5) * 1.15
            cz = (row - 1) * 1.3
            # Tilted panel plane (approximated with a thin rotated box)
            h = math.cos(tilt) * 0.02
            pos, idx = _box_chunk(cx, 0.35 + row * 0.06, cz + row * 0.28, 1.0, h, 0.9)
            parts.append((f"panel_{row}_{col}", pos, idx, panel_mat))

    # Support legs
    for row in range(3):
        for col in (0, 3):
            cx = (col - 1.5) * 1.15
            cz = (row - 1) * 1.3 + row * 0.28
            pos, idx = _box_chunk(cx, 0.15, cz, 0.08, 0.4, 0.08)
            parts.append((f"leg_{row}_{col}", pos, idx, frame_mat))
    return parts


def battery_bank():
    """Cabinet with 3×4 stacked battery modules."""
    parts = []
    cabinet_mat = {"name": "cabinet", "color": [0.18, 0.22, 0.26, 1.0], "metallic": 0.3}
    module_mat = {"name": "module", "color": [0.12, 0.55, 0.42, 1.0], "metallic": 0.5, "roughness": 0.4}

    pos, idx = _box_chunk(0, 0.55, 0, 1.2, 1.1, 0.8)
    parts.append(("cabinet", pos, idx, cabinet_mat))
    for r in range(3):
        for c in range(4):
            pos, idx = _box_chunk(
                (c - 1.5) * 0.26, 0.25 + r * 0.3, 0.0, 0.22, 0.24, 0.6
            )
            parts.append((f"module_{r}_{c}", pos, idx, module_mat))
    return parts


def wind_turbine():
    """Tower + hub; rotor blades added in code for animation."""
    parts = []
    tower_mat = {"name": "tower", "color": [0.9, 0.9, 0.92, 1.0], "metallic": 0.2}
    hub_mat = {"name": "hub", "color": [0.75, 0.78, 0.8, 1.0], "metallic": 0.4}

    pos, idx = _cylinder_chunks(0, 1.5, 0, 0.12, 3.0, 12)
    parts.append(("tower", pos, idx, tower_mat))
    pos, idx = _cylinder_chunks(0, 3.1, 0, 0.28, 0.5, 12)
    parts.append(("hub", pos, idx, hub_mat))
    return parts


def ev_charger():
    """Charging post with a status panel."""
    parts = []
    body_mat = {"name": "charger_body", "color": [0.24, 0.26, 0.3, 1.0], "metallic": 0.3}
    panel_mat = {"name": "status_panel", "color": [0.1, 0.75, 0.6, 1.0], "metallic": 0.2, "roughness": 0.3}

    pos, idx = _box_chunk(0, 0.45, 0, 0.35, 0.9, 0.25)
    parts.append(("body", pos, idx, body_mat))
    pos, idx = _box_chunk(0, 0.72, 0.14, 0.24, 0.18, 0.03)
    parts.append(("panel", pos, idx, panel_mat))
    return parts


def hospital():
    """Critical facility: main block + emergency wing."""
    parts = []
    wall_mat = {"name": "walls", "color": [0.92, 0.93, 0.95, 1.0]}
    red_mat = {"name": "emergency", "color": [0.85, 0.15, 0.15, 1.0]}

    pos, idx = _box_chunk(0, 0.5, 0, 1.8, 1.0, 1.2)
    parts.append(("main", pos, idx, wall_mat))
    pos, idx = _box_chunk(1.15, 0.35, 0, 0.6, 0.7, 0.8)
    parts.append(("wing", pos, idx, wall_mat))
    pos, idx = _box_chunk(0, 1.06, 0, 0.4, 0.12, 0.4)
    parts.append(("roof_sign", pos, idx, red_mat))
    return parts


if __name__ == "__main__":
    print("Generating GridMind glTF assets…")
    build_gltf(solar_array(), OUT_DIR / "solar_array.gltf")
    build_gltf(battery_bank(), OUT_DIR / "battery_bank.gltf")
    build_gltf(wind_turbine(), OUT_DIR / "wind_turbine.gltf")
    build_gltf(ev_charger(), OUT_DIR / "ev_charger.gltf")
    build_gltf(hospital(), OUT_DIR / "hospital.gltf")
    print("Done.")
