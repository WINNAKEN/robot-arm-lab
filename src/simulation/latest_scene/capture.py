"""Native Replicator capture. Importing this module does not initialize Isaac."""
from fractions import Fraction
import hashlib
import math
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


def validate_generation(metrics):
    """Fail closed on stale RGB, reference, dispatcher, or incomplete scheduling."""
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


class NativeCapture:
    def __init__(self, ctx, stage, program):
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
        config = program['camera']
        camera = UsdGeom.Camera.Define(stage, config['path'])
        matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*config['eye']), Gf.Vec3d(*config['target']), Gf.Vec3d(0, 0, 1)).GetInverse()
        camera.AddTransformOp().Set(matrix)
        camera.GetFocalLengthAttr().Set(config['focal_length_mm'])
        camera.GetHorizontalApertureAttr().Set(config['horizontal_aperture_mm'])
        camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
        light = UsdLux.DomeLight.Define(stage, '/World/DomeLight')
        light.GetIntensityAttr().Set(1500.0)
        self.product = rep.create.render_product(config['path'], tuple(program['resolution']), force_new=True)
        self.product_path = str(self.product.path)
        self.rgb = rep.AnnotatorRegistry.get_annotator('rgb', device='cpu')
        self.reference = rep.AnnotatorRegistry.get_annotator('ReferenceTime', device='cpu')
        self.rgb.attach([self.product])
        self.reference.attach([self.product])
        rep.orchestrator.set_capture_on_play(False)
        # Exactly one planned, unrecorded warmup. Never retry a failed capture.
        rep.orchestrator.step(rt_subframes=1, pause_timeline=False, delta_time=0.0, wait_for_render=True)
        require(self.timeline.is_stopped(), 'Warmup changed the stopped timeline')
        # Keep the actual OG wrappers alive: Python wrapper IDs are provenance,
        # not native graph-node IDs. Native generation evidence comes from compute_count.
        self._nodes = {'rgb': self.rgb.get_node(), 'reference': self.reference.get_node(),
                       'dispatcher': self.og.get_node_by_path('/Render/PostProcess/SDGPipeline/PostProcessDispatcher')}
        self.warmup = {'timeline_stopped': True, 'nodes': self.nodes(), 'render_product': self.product_path}
        self.directory = ctx.run / 'output' / 'frames'
        self.directory.mkdir(parents=True, exist_ok=False)
        self.hashes = set()

    def nodes(self):
        result = {}
        for name, node in self._nodes.items():
            require(bool(node), 'Missing OG capture node: ' + name)
            result[name] = {'path': str(node.get_prim_path()), 'id': id(node), 'id_kind': 'PYTHON_WRAPPER',
                            'type': str(node.get_node_type()), 'compute_count': int(node.get_compute_count())}
        return result

    def capture(self, index, row, state_getter):
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
        metrics = {'before': before, 'after': after, 'scheduled': [int(x) for x in scheduled],
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
        require(native_before == native_after, 'Native clock, step or physical state changed during render')
        from PIL import Image
        target = self.directory / ('frame-%04d.png' % index)
        Image.fromarray(pixels, mode='RGBA').save(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        self.hashes.add(digest)
        frame = {'frame_index': index, 'state_index': row['step'], 'physics_time_s': row['time_s'],
                 'phase': row['phase'], 'targets': row['targets'], 'png': 'frames/' + target.name,
                 'sha256': digest, 'freshness': metrics, 'native_before': native_before,
                 'native_after': native_after, 'pixel_shape': list(pixels.shape), 'pixel_dtype': str(pixels.dtype)}
        self.ctx.write(target.with_suffix('.json'), frame)
        self.ctx.write(pending_path, {'status': 'CAPTURE_COMPLETE', 'frame_index': index,
                                     'state_index': row['step'], 'png': frame['png'], 'sha256': digest})
        return frame

    def finish(self, count):
        require(len(self.hashes) > 1, 'All scene image hashes are identical')
        require(len(list(self.directory.glob('frame-*.png'))) == count, 'Exact native PNG inventory required')
        require(len(list(self.directory.glob('frame-*.json'))) == count, 'Exact frame sidecar inventory required')
        return {'passed': True, 'frames': count, 'unique_png_hashes': len(self.hashes), 'warmup': self.warmup}
