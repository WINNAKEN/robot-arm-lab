"""Software preview of actual written URDF/STL; no CAD or simulator mutation."""
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def render(package, root):
    from PIL import Image, ImageDraw, ImageFont
    from verify import stl_triangles, urdf_fk, apply
    package = Path(package)
    robot = ET.parse(package / 'robot_arm.urdf').getroot()
    poses = [([0., 0., 0.], [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])] + urdf_fk(robot.findall('joint'), [0.]*6)
    colours = {}
    for m in robot.findall('material'):
        colours[m.get('name')] = [int(float(x)*255) for x in m.find('color').get('rgba').split()[:3]]
    faces, projected = [], []
    def project(v):
        return [(v[0]-v[1])*.866025403784, v[2]-.5*(v[0]+v[1])]
    for link, (origin, rotation) in zip(robot.findall('link'), poses):
        for visual in link.findall('visual'):
            colour = colours[visual.find('material').get('name')]
            for triangle in stl_triangles(package / visual.find('geometry/mesh').get('filename')):
                world = [[a+b for a, b in zip(origin, apply(rotation, p))] for p in triangle]
                screen = [project(v) for v in world]
                projected.extend(screen)
                u, v = [[world[j][k]-world[0][k] for k in range(3)] for j in (1, 2)]
                normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                length = math.sqrt(sum(x*x for x in normal))
                light = .62+.38*abs(sum(normal)/(math.sqrt(3)*length)) if length else .62
                faces.append((sum(sum(w) for w in world), screen, tuple(min(255, int(x*light)) for x in colour)))
    lo = [min(v[k] for v in projected) for k in range(2)]
    hi = [max(v[k] for v in projected) for k in range(2)]
    image = Image.new('RGB', (1100, 920), '#f4f6f8')
    draw = ImageDraw.Draw(image)
    scale = min(950/(hi[0]-lo[0]), 710/(hi[1]-lo[1]))
    def pixel(v):
        return (550+(v[0]-(lo[0]+hi[0])/2)*scale, 480-(v[1]-(lo[1]+hi[1])/2)*scale)
    for _, points, colour in sorted(faces, key=lambda f: f[0]):
        draw.polygon([pixel(p) for p in points], fill=colour)
    font, small = ImageFont.load_default(size=26), ImageFont.load_default(size=17)
    draw.text((32, 22), 'CAD v2 -> URDF simulation draft', font=font, fill='#162a40')
    draw.text((32, 58), '7 links / 6 revolute joints / q=0: original CAD display pose', font=small, fill='#44566b')
    for i, (p, _) in enumerate(poses[1:], 1):
        x, y = pixel(project(p))
        draw.ellipse((x-4, y-4, x+4, y+4), fill='#14a57b', outline='white', width=1)
        draw.text((x+7, y-12), f'J{i}', font=small, fill='#087455', stroke_width=1, stroke_fill='#f4f6f8')
    draw.text((32, 854), 'Mass / COM / inertia / collision proxies / limits: ASSUMED', font=small, fill='#a44610')
    draw.text((32, 883), 'Isaac import and RL: NOT RUN. No calibration or motor operation.', font=small, fill='#44566b')
    image.save(package / 'preview.png')
