"""124 local candidate: reset only fresh anonymous USD layers. No SDK imports."""


def fresh_stage(ctx, context, clock):
    """Establish strict emptiness and preserve failed observations before raising."""
    import hashlib
    import math

    packet = {'schema_version': 1, 'verified': False, 'before': None,
              'after_new': None, 'after': None, 'cleared_layers': []}
    target = ctx.run / 'output/fresh-stage.json'

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def persist():
        ctx.write(target, packet)

    def stamp(name):
        value = float(clock())
        packet[name] = value if math.isfinite(value) else {'invalid': repr(value)}
        return value

    def census(stage):
        if stage is None:
            return None
        default = stage.GetDefaultPrim()
        return {
            'layer': str(stage.GetRootLayer().identifier),
            'session_layer': str(stage.GetSessionLayer().identifier),
            'layer_stack': [str(layer.identifier) for layer in stage.GetLayerStack()],
            'used_layers': [str(layer.identifier) for layer in stage.GetUsedLayers()],
            'default_prim': str(default.GetPath()) if default else None,
            'prims': [{'path': str(prim.GetPath()), 'type': str(prim.GetTypeName()),
                       'applied_schemas': list(prim.GetAppliedSchemas())}
                      for prim in stage.TraverseAll()],
        }

    def signature(layer):
        return hashlib.sha256(layer.ExportToString().encode('utf8')).hexdigest()

    try:
        persist()  # If observation cannot be saved, do not create or clear a stage.
        old = context.get_stage()
        old_roots = [] if old is None else [old.GetRootLayer(), old.GetSessionLayer()]
        old_layers = [] if old is None else list(old.GetLayerStack()) + list(old.GetUsedLayers())
        old_ids = {str(layer.identifier) for layer in old_layers}
        packet['before'] = census(old)
        before_time = stamp('engine_before_s')
        persist()
        require(math.isfinite(before_time) and before_time == 0., 'Zero engine clock before fresh stage')

        result = context.new_stage()
        new = context.get_stage()
        packet['after_new'] = census(new)
        new_time = stamp('engine_after_new_s')
        persist()  # The original failure lost precisely this census.
        require(result is not False and new is not None, 'Actual fresh stage created')
        root, session = new.GetRootLayer(), new.GetSessionLayer()
        layers = [root, session]
        new_ids = {str(layer.identifier) for layer in layers}
        require(len(new_ids) == 2 and all(layer.anonymous is True for layer in layers),
                'Two distinct anonymous new layers required')
        require(not (new_ids & old_ids), 'New layers must not share any old layer')
        require(old is None or str(root.identifier) != packet['before']['layer'],
                'Distinct actual fresh root identity')
        require(math.isfinite(new_time) and new_time == before_time == 0.,
                'Zero engine clock after stage creation')
        packet['old_layers_before_reset'] = {str(layer.identifier): signature(layer) for layer in old_roots}
        packet['owned_reset_layers'] = sorted(new_ids)
        persist()

        for index, layer in enumerate(layers):
            current = context.get_stage()
            require(current is not None and current.GetRootLayer() == root and
                    current.GetSessionLayer() == session,
                    'Owned layers must remain current before Clear')
            value = stamp('engine_before_clear_%d_s' % index)
            require(math.isfinite(value) and value == 0., 'Zero engine clock before Clear')
            require(layer.anonymous is True and str(layer.identifier) in new_ids and
                    str(layer.identifier) not in old_ids, 'Clear only a fresh owned anonymous layer')
            layer.Clear()
            packet['cleared_layers'].append(str(layer.identifier))

        current = context.get_stage()
        packet['after'] = census(current)
        after_time = stamp('engine_after_s')
        packet['old_layers_after_reset'] = {str(layer.identifier): signature(layer) for layer in old_roots}
        persist()
        require(current is not None and current.GetRootLayer() == root and
                current.GetSessionLayer() == session, 'Owned layers remain current after Clear')
        require(all(layer.empty is True for layer in layers), 'Both owned layers must actually be empty')
        require(set(packet['after']['layer_stack']) == new_ids and
                not (set(packet['after']['used_layers']) & old_ids), 'No inherited old layer after reset')
        require(packet['after']['prims'] == [] and packet['after']['default_prim'] is None,
                'Fresh stage has no inherited roots or objects')
        require(math.isfinite(after_time) and after_time == new_time == before_time == 0.,
                'Fresh stage preserves zero engine clock')
        require(packet['old_layers_before_reset'] == packet['old_layers_after_reset'],
                'Old root and session content must remain unchanged')
        packet['verified'] = True
        persist()
        return current
    except Exception as primary:
        packet['verified'] = False
        packet['error'] = type(primary).__name__ + ': ' + str(primary)
        try:
            packet['failure_census'] = census(context.get_stage())
        except Exception as observation_error:
            packet['failure_census_error'] = type(observation_error).__name__ + ': ' + str(observation_error)
        try:
            persist()
        except Exception as write_error:
            primary.add_note('Failed to persist stage evidence: ' + type(write_error).__name__ + ': ' + str(write_error))
        raise
