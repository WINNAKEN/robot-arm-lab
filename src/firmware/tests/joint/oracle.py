"""Generate fixed-source021 conversion oracle, no CAD or hardware execution."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    pins = {
        'src/joint_frames/frames.py': '1eb5d41f439e5201ce0b0c5ee53222584082b8446bfef2e00a5bdd3eed5b4d46',
        'models/armold-mks-concept-v1/kinematics.json': 'fe000e47a3885566a9ca808b053f429e13272da97a8dac132cb44b6153eeae50',
        '.dev/joint-frames-evidence/l4-r2.md': 'fdd4030257d77b51e9077d1e8cbd1425dd036a70f9ffa4be13ae96e3ba5f5138',
        '.dev/native-direction-evidence/l4-r1.md': 'a5b231ab37eaadd2bbf548b477120110446f10ece64f98fae89c60302843ab56',
    }
    raw = {p: (root/p).read_bytes() for p in pins}
    for path, digest in pins.items():
        if hashlib.sha256(raw[path]).hexdigest() != digest:
            raise ValueError('Unapproved oracle source: '+path)
    path = root/'src/joint_frames/frames.py'
    spec = importlib.util.spec_from_file_location('joint_oracle_approved021', path)
    core = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = core
    exec(compile(raw['src/joint_frames/frames.py'], str(path), 'exec'), core.__dict__)
    layout = core.decode(raw['models/armold-mks-concept-v1/kinematics.json'])
    rows = []
    for joint in range(1, 7):
        for space in range(3):
            values = [-30., -5., 0., 5., 30., 55.25, -71.25] if space == 0 else [-math.pi, -1.234, -.1, 0., .1, 1.234, math.pi]
            for value in values:
                angles = [0.]*6
                angles[joint-1] = math.radians(value) if space == 0 else value
                delta = core.geometric_to_delta(layout, angles) if space == 2 else angles
                geometric = core.delta_to_geometric(layout, delta)
                d = delta[joint-1]
                rows.append((joint, space, value, math.degrees(d), d, geometric[joint-1]))
    text = '#include <array>\nstruct Oracle {unsigned joint,space;double input,cad,delta,geometric;};\n'
    text += 'const std::array<Oracle,'+str(len(rows))+'> oracle{{\n'
    text += ',\n'.join('    {'+','.join(str(v) for v in row)+'}' for row in rows)+'\n}};\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(text.encode('utf-8'))
    args.out.with_suffix('.meta.json').write_bytes((json.dumps({'source_pins': pins, 'rows': len(rows), 'oracle_sha256': hashlib.sha256(text.encode()).hexdigest()}, indent=2)+'\n').encode())
    print('approved021 oracle rows='+str(len(rows)))


if __name__ == '__main__':
    main()
