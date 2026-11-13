"""Native Replicator capture. Importing this module does not initialize Isaac."""
from fractions import Fraction
import hashlib
import math
import itertools
import struct
import sys
import zlib
from pathlib import Path


class CaptureError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CaptureError(message)


def rational(value):
    require(type(value) in (list, tuple) and len(value) == 2, 'Rational pair required')
    require(all(type(v) is int for v in value) and value[1] > 0, 'Exact rational integers required')
    return Fraction(*value)


REFERENCE_CLOCK_DENOMINATOR=1_000_000_000
SCHEDULE_QUANTIZATION='FLOAT64_RATIONAL_MULTIPLY_1E9_TRUNCATE'


def encode_scheduled_reference(source_raw):
    value=rational(source_raw)
    return [int(float(value)*REFERENCE_CLOCK_DENOMINATOR),REFERENCE_CLOCK_DENOMINATOR]


def validate_generation(metrics):
    """Fail closed on stale RGB, reference, dispatcher, or incomplete scheduling."""
    require(metrics['quantization_rule']==SCHEDULE_QUANTIZATION and
            metrics['scheduled']==encode_scheduled_reference(metrics['scheduled_source_raw']),
            'Exact source schedule encoding into the native integer ReferenceTime clock')
    binary=float(rational(metrics['scheduled_source_raw']))
    require(type(metrics['source_engine_time_s']) is float and math.isfinite(binary) and binary>=0 and metrics['source_engine_time_s']==binary and metrics['scheduled_binary64_hex']==binary.hex(),'Exact binary64 schedule and actual engine clock')
    for name in ('rgb', 'reference', 'dispatcher'):
        a, b = metrics['before'][name], metrics['after'][name]
        require(all(a[k] == b[k] for k in ('path', 'id', 'type')), 'Render node identity changed: ' + name)
        require(type(a['compute_count']) is int and type(b['compute_count']) is int,
                'Actual integer compute generation required')
        require(a['id'] > 0 and a['path'] and a['type'], 'Missing render node: ' + name)
        require(b['compute_count'] > a['compute_count'] >= 0, 'Stale render generation: ' + name)
    require(rational(metrics['dispatcher_reference']) >= rational(metrics['scheduled']),
            'Renderer did not reach scheduled reference time')
    require(rational(metrics['render_product_reference']) == rational(metrics['dispatcher_reference']),
            'Render-product reference differs from dispatcher')
    require(bool(metrics['render_product']), 'Missing render-product binding')
    log = metrics.get('renderer_log', '').lower()
    require('renderer failed to advance to the scheduled frame' not in log and
            'step scheduling failed' not in log and 'failed to schedule' not in log,
            'Renderer reported a scheduling failure')
    return True


def validate_pixels(pixels):
    require(str(pixels.dtype) == 'uint8' and tuple(pixels.shape) == (480, 640, 4),
            'Native RGB must be uint8 RGBA 480x640x4')
    require(int(pixels[:, :, :3].max()) > int(pixels[:, :, :3].min()), 'Blank native RGB image')
    # A single bright or dark pixel must not turn an otherwise blank render into evidence.
    require(float(pixels[:, :, :3].std()) > 1.0, 'Near-blank native RGB image')


def encode_rgba_png(pixels):
    require(str(pixels.dtype)=='uint8' and tuple(pixels.shape)==(480,640,4), 'Actual RGBA8 buffer shape')
    raw=pixels.tobytes(order='C')
    require(type(raw) is bytes and len(raw)==480*640*4, 'Complete actual pixel bytes')
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    rows=b''.join(b'\0'+raw[i*640*4:(i+1)*640*4] for i in range(480))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',640,480,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows,1))+chunk(b'IEND',b'')
    return png,hashlib.sha256(raw).hexdigest()


def wrapper_metadata(value,methods):
    cls=type(value);module=sys.modules.get(cls.__module__)
    return {'module':cls.__module__,'class':cls.__qualname__,
            'module_file':getattr(module,'__file__',None),
            'capabilities':{name:callable(getattr(value,name,None)) for name in methods}}


def validate_node_capabilities(metadata):
    require(set(metadata)=={'rgb','reference','dispatcher'} and
            all(set(row['capabilities'])=={'get_prim_path','get_type_name','get_compute_count','get_attribute'}
                and all(value is True for value in row['capabilities'].values()) for row in metadata.values()),
            'Actual graph wrapper methods before first capture')


def validate_render_binding(before,after):
    require(before==after,'Native clock, step or physical state changed during render')


def validate_camera_envelope(config):
    eye=config['eye'];target=config['target'];bounds=config['union_bounds']
    forward=[target[i]-eye[i] for i in range(3)];length=math.sqrt(sum(x*x for x in forward))
    require(length>0,'Camera eye differs from target');forward=[x/length for x in forward]
    right=[forward[1],-forward[0],0.];length=math.sqrt(sum(x*x for x in right))
    require(length>0,'Camera up is nondegenerate');right=[x/length for x in right]
    up=[right[1]*forward[2]-right[2]*forward[1],right[2]*forward[0]-right[0]*forward[2],right[0]*forward[1]-right[1]*forward[0]]
    fractions=[]
    for point in itertools.product(*zip(bounds['min'],bounds['max'])):
        delta=[point[i]-eye[i] for i in range(3)];depth=sum(x*y for x,y in zip(delta,forward))
        require(depth>0,'Camera envelope is in front')
        fractions.extend((abs(sum(x*y for x,y in zip(delta,right)))/(depth*config['horizontal_aperture_mm']/(2*config['focal_length_mm'])),
                          abs(sum(x*y for x,y in zip(delta,up)))/(depth*config['vertical_aperture_mm']/(2*config['focal_length_mm']))))
    require(max(fractions)<=1/config['margin_factor'],'Whole envelope camera margin')
    return max(fractions)


def camera_for_workspace(program,workspace):
    a,b=workspace['cloud']['bbox'],workspace['planned_body_bounds']
    lo=[min(a['min'][i],b['min'][i]) for i in range(3)];hi=[max(a['max'][i],b['max'][i]) for i in range(3)]
    require(all(math.isfinite(v) for v in lo+hi) and all(lo[i]<hi[i] for i in range(3)), 'Finite complete camera envelope')
    config=dict(program['camera']);center=[(x+y)/2 for x,y in zip(lo,hi)]
    direction=[1.4,-1.6,1.0];norm=math.sqrt(sum(v*v for v in direction));direction=[v/norm for v in direction]
    forward=[-v for v in direction]
    right=[forward[1],-forward[0],0.];norm=math.sqrt(sum(v*v for v in right));right=[v/norm for v in right]
    up=[right[1]*forward[2]-right[2]*forward[1],right[2]*forward[0]-right[0]*forward[2],right[0]*forward[1]-right[1]*forward[0]]
    focal=config['focal_length_mm'];horizontal=config['horizontal_aperture_mm'];vertical=config.get('vertical_aperture_mm',horizontal*480/640)
    require(focal>0 and horizontal>0 and vertical>0,'Actual positive camera optics')
    tan_h=horizontal/(2*focal);tan_v=vertical/(2*focal)
    radius=math.sqrt(sum(((y-x)/2)**2 for x,y in zip(lo,hi)))
    distance=radius/math.sin(math.atan(min(tan_h,tan_v)))*1.15
    corners=list(itertools.product(*zip(lo,hi)))
    for _ in range(8):
        eye=[center[i]+direction[i]*distance for i in range(3)];fractions=[]
        for point in corners:
            delta=[point[i]-eye[i] for i in range(3)];depth=sum(x*y for x,y in zip(delta,forward))
            require(depth>0,'Camera envelope in front of camera')
            fractions.extend((abs(sum(x*y for x,y in zip(delta,right)))/(depth*tan_h),abs(sum(x*y for x,y in zip(delta,up)))/(depth*tan_v)))
        maximum=max(fractions)
        if maximum<=1/1.15:break
        distance*=maximum*1.15*1.001
    require(maximum<=1/1.15,'Whole cloud and planned body envelope with 15 percent margin')
    config.update(eye=eye,target=center,vertical_aperture_mm=vertical,
                  union_bounds={'min':lo,'max':hi},margin_factor=1.15,max_projected_fraction=maximum)
    validate_camera_envelope(config)
    return config


class NativeCapture:
    def __init__(self, ctx, stage, program, workspace):
        import omni.graph.core as og
        import omni.kit.app
        import omni.timeline
        import omni.replicator.core as rep
        from pxr import Gf, UsdGeom, UsdLux
        self.ctx, self.og, self.rep = ctx, og, rep
        self.timeline = omni.timeline.get_timeline_interface()
        require(self.timeline.is_stopped(), 'Camera warmup must begin while timeline is stopped')
        manager = omni.kit.app.get_app().get_extension_manager()
        ctx.scene_modules['sdk'].enable('omni.kit.viewport.window')
        require(manager.is_extension_enabled('omni.kit.viewport.window'), 'Viewport extension activation failed')
        config = camera_for_workspace(program,workspace)
        self.camera=config
        camera = UsdGeom.Camera.Define(stage, config['path'])
        matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*config['eye']), Gf.Vec3d(*config['target']), Gf.Vec3d(0, 0, 1)).GetInverse()
        camera.AddTransformOp().Set(matrix)
        camera.GetFocalLengthAttr().Set(config['focal_length_mm'])
        camera.GetHorizontalApertureAttr().Set(config['horizontal_aperture_mm'])
        camera.GetVerticalApertureAttr().Set(config['vertical_aperture_mm'])
        camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
        light = UsdLux.DomeLight.Define(stage, '/World/DomeLight')
        light.GetIntensityAttr().Set(1500.0)
        self.product = rep.create.render_product(config['path'], tuple(program['resolution']), force_new=True)
        self.product_path = str(self.product.path)
        self.rgb = rep.AnnotatorRegistry.get_annotator('rgb', device='cpu')
        self.reference = rep.AnnotatorRegistry.get_annotator('ReferenceTime', device='cpu')
        self.rgb.attach([self.product])
        self.reference.attach([self.product])
        api={'product':wrapper_metadata(self.product,()),'product_path':self.product_path,
             'rgb':wrapper_metadata(self.rgb,('get_node','get_data')),
             'reference':wrapper_metadata(self.reference,('get_node','get_data'))}
        ctx.write(ctx.run/'output/capture-api.json',api)
        require(self.product_path.startswith('/'),'Actual render product path')
        require(all(api[k]['capabilities'][m] for k in ('rgb','reference') for m in ('get_node','get_data')),
                'Actual annotator wrapper methods')
        rep.orchestrator.set_capture_on_play(False)
        # Exactly one planned, unrecorded warmup. Never retry a failed capture.
        rep.orchestrator.step(rt_subframes=1, pause_timeline=False, delta_time=0.0, wait_for_render=True)
        require(self.timeline.is_stopped(), 'Warmup changed the stopped timeline')
        # Keep the actual OG wrappers alive: Python wrapper IDs are provenance,
        # not native graph-node IDs. Native generation evidence comes from compute_count.
        self._nodes = {'rgb': self.rgb.get_node(), 'reference': self.reference.get_node(),
                       'dispatcher': self.og.get_node_by_path('/Render/PostProcess/SDGPipeline/PostProcessDispatcher')}
        api['nodes']={name:wrapper_metadata(node,('get_prim_path','get_type_name','get_compute_count','get_attribute')) for name,node in self._nodes.items()}
        ctx.write(ctx.run/'output/capture-api.json',api)
        validate_node_capabilities(api['nodes'])
        self.warmup = {'timeline_stopped': True, 'nodes': self.nodes(), 'render_product': self.product_path}
        self.directory = ctx.run / 'output' / 'frames'
        self.directory.mkdir(parents=True, exist_ok=False)
        self.hashes = set()

    def nodes(self):
        result = {}
        for name, node in self._nodes.items():
            require(bool(node), 'Missing OG capture node: ' + name)
            result[name] = {'path': str(node.get_prim_path()), 'id': id(node), 'id_kind': 'PYTHON_WRAPPER',
                            'type': str(node.get_type_name()), 'compute_count': int(node.get_compute_count())}
        return result

    def capture(self, index, row, state_getter, tcp_visual=None):
        native_before = state_getter()
        before = self.nodes()
        pending = {'status': 'CAPTURE_REQUESTED', 'frame_index': index, 'state_index': row['step'],
                   'physics_time_s': row['time_s'], 'phase': row['phase'],
                   'native_before': native_before, 'nodes_before': before}
        pending_path = self.directory.parent/'capture-pending.json'
        self.ctx.write(pending_path, pending)
        self.rep.orchestrator.step(rt_subframes=1, pause_timeline=False, delta_time=0.0, wait_for_render=True)
        after = self.nodes()
        scheduled = list(self.rep.orchestrator._orchestrator._sim_times_to_write[-1])
        dispatcher = self._nodes['dispatcher']
        dispatched = [dispatcher.get_attribute('outputs:referenceTimeNumerator').get(),
                      dispatcher.get_attribute('outputs:referenceTimeDenominator').get()]
        reference = self.reference.get_data(device='cpu', do_array_copy=True)
        ref = [reference['referenceTimeNumerator'], reference['referenceTimeDenominator']]
        scheduled_source_raw=[int(x) for x in scheduled]
        metrics = {'before': before, 'after': after, 'scheduled': encode_scheduled_reference(scheduled_source_raw),
                   'scheduled_source_raw':scheduled_source_raw,'scheduled_binary64_hex':float(rational(scheduled_source_raw)).hex(),'source_engine_time_s':native_before['clock']['engine_time_s'],'quantization_rule':SCHEDULE_QUANTIZATION,
                   'dispatcher_reference': [int(x) for x in dispatched],
                   'render_product_reference': [int(x) for x in ref], 'render_product': self.product_path}
        pending.update(status='GENERATIONS_OBSERVED', freshness=metrics)
        self.ctx.write(pending_path, pending)
        validate_generation(metrics)
        pixels = self.rgb.get_data(device='cpu', do_array_copy=True)
        native_after = state_getter()
        pending.update(status='PIXELS_OBSERVED', native_after=native_after,
                       pixel_shape=list(pixels.shape), pixel_dtype=str(pixels.dtype))
        self.ctx.write(pending_path, pending)
        validate_pixels(pixels)
        validate_render_binding(native_before,native_after)
        target = self.directory / ('frame-%04d.png' % index)
        encoded,rgba_sha256=encode_rgba_png(pixels)
        with target.open('xb') as stream:stream.write(encoded)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        self.hashes.add(digest)
        frame = {'frame_index': index, 'state_index': row['step'], 'physics_time_s': row['time_s'],
                 'phase': row['phase'], 'targets': row['targets'], 'png': 'frames/' + target.name,
                 'sha256': digest, 'freshness': metrics, 'native_before': native_before,
                 'native_after': native_after, 'pixel_shape': list(pixels.shape), 'pixel_dtype': str(pixels.dtype),
                 'rgba_sha256':rgba_sha256,'png_encoding':'RGBA8_FILTER0_ZLIB1'}
        frame['actual_tcp']=row['actual_tcp']
        frame['actual_tcp_visual']=tcp_visual
        self.ctx.write(target.with_suffix('.json'), frame)
        self.ctx.write(pending_path, {'status': 'CAPTURE_COMPLETE', 'frame_index': index,
                                     'state_index': row['step'], 'png': frame['png'], 'sha256': digest})
        return frame

    def finish(self, count, purpose='motion'):
        require(purpose in ('render_smoke','motion'),'Closed capture purpose')
        require(len(self.hashes) >= 1 if purpose=='render_smoke' else len(self.hashes)>1,
                'Purpose-specific actual image hash policy')
        require(len(list(self.directory.glob('frame-*.png'))) == count, 'Exact native PNG inventory required')
        require(len(list(self.directory.glob('frame-*.json'))) == count, 'Exact frame sidecar inventory required')
        return {'passed': True, 'frames': count, 'unique_png_hashes': len(self.hashes), 'warmup': self.warmup}
