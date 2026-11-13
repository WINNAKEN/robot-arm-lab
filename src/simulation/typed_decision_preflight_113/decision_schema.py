"""113 closed-format decision input policy. It reads only supplied byte strings."""
import hashlib
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from types import MappingProxyType

ROLE_CONTRACT_SHA = '698307f7ece43d64e9d0d044553d6b5bbcf3237545f1630c7577d8975faaf4a8'
# JSON_ROLES is inserted from the L2-pinned semantic IR, never candidate values.
JSON_ROLES = {'model/asset-ledger.json': {'kind': 'object',
                             'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                             'required': {'links': {'kind': 'mapping',
                                                    'min_entries': 1,
                                                    'value': {'kind': 'object',
                                                              'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                              'required': {'box_size_m': {'exact_length': 3,
                                                                                          'item': {'kind': 'number'},
                                                                                          'kind': 'array',
                                                                                          'min_length': 1},
                                                                           'com_m': {'exact_length': 3,
                                                                                     'item': {'kind': 'number'},
                                                                                     'kind': 'array',
                                                                                     'min_length': 1},
                                                                           'inertia_kg_m2': {'exact_length': 3,
                                                                                             'item': {'kind': 'number'},
                                                                                             'kind': 'array',
                                                                                             'min_length': 1},
                                                                           'mass_kg': {'kind': 'number'},
                                                                           'triangles': {'kind': 'integer'}}}},
                                          'source_items': {'exact_length': None,
                                                           'item': {'kind': 'object',
                                                                    'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                    'required': {'printed': {'kind': 'boolean'},
                                                                                 'triangles': {'kind': 'integer'}}},
                                                           'kind': 'array',
                                                           'min_length': 1}}},
 'model/manifest.json': {'kind': 'object',
                         'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                         'required': {}},
 'model/provenance.json': {'kind': 'object',
                           'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                           'required': {'input_census': {'kind': 'mapping',
                                                         'min_entries': 1,
                                                         'value': {'kind': 'object',
                                                                   'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                   'required': {'bytes': {'kind': 'integer'}}}}}},
 'ref/model-submission.json': {'kind': 'object',
                               'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                               'required': {'canonical_current_binding': {'kind': 'boolean'},
                                            'fresh_controls': {'kind': 'integer'},
                                            'source_and_evidence_count': {'kind': 'integer'},
                                            'source_and_evidence_files': {'kind': 'mapping',
                                                                          'min_entries': 1,
                                                                          'value': {'kind': 'object',
                                                                                    'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                    'required': {'bytes': {'kind': 'integer'}}}}}},
 'ref/prefix-seal.json': {'kind': 'object',
                          'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                          'required': {'schema_version': {'kind': 'integer'}}},
 'ref/workspace.json': {'kind': 'object',
                        'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                        'required': {'cloud': {'kind': 'object',
                                               'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                               'required': {'bbox': {'kind': 'object',
                                                                     'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                     'required': {'max': {'exact_length': 3,
                                                                                          'item': {'kind': 'number'},
                                                                                          'kind': 'array',
                                                                                          'min_length': 1},
                                                                                  'min': {'exact_length': 3,
                                                                                          'item': {'kind': 'number'},
                                                                                          'kind': 'array',
                                                                                          'min_length': 1}}},
                                                            'collision': {'kind': 'boolean'},
                                                            'opacity': {'kind': 'number'},
                                                            'render_indices': {'exact_length': None,
                                                                               'item': {'kind': 'integer'},
                                                                               'kind': 'array',
                                                                               'min_length': 1},
                                                            'voxels': {'exact_length': None,
                                                                       'item': {'kind': 'object',
                                                                                'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                'required': {'count': {'kind': 'integer'},
                                                                                             'key': {'exact_length': 3,
                                                                                                     'item': {'kind': 'integer'},
                                                                                                     'kind': 'array',
                                                                                                     'min_length': 1},
                                                                                             'position': {'exact_length': 3,
                                                                                                          'item': {'kind': 'number'},
                                                                                                          'kind': 'array',
                                                                                                          'min_length': 1},
                                                                                             'witness_index': {'kind': 'integer'}}},
                                                                       'kind': 'array',
                                                                       'min_length': 1},
                                                            'width_m': {'kind': 'number'}}},
                                     'effort_limits': {'kind': 'object',
                                                       'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                       'required': {'J1': {'kind': 'number'},
                                                                    'J2': {'kind': 'number'},
                                                                    'J3': {'kind': 'number'},
                                                                    'J4': {'kind': 'number'},
                                                                    'J5': {'kind': 'number'},
                                                                    'J6': {'kind': 'number'},
                                                                    'KG1_pinion': {'kind': 'number'},
                                                                    'KG1_slide_A': {'kind': 'number'},
                                                                    'KG1_slide_B': {'kind': 'number'}}},
                                     'gravity': {'exact_length': 3,
                                                 'item': {'kind': 'number'},
                                                 'kind': 'array',
                                                 'min_length': 1},
                                     'joint_limits_rad': {'kind': 'object',
                                                          'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                          'required': {'J1': {'exact_length': 2,
                                                                              'item': {'kind': 'number'},
                                                                              'kind': 'array',
                                                                              'min_length': 1},
                                                                       'J2': {'exact_length': 2,
                                                                              'item': {'kind': 'number'},
                                                                              'kind': 'array',
                                                                              'min_length': 1},
                                                                       'J3': {'exact_length': 2,
                                                                              'item': {'kind': 'number'},
                                                                              'kind': 'array',
                                                                              'min_length': 1},
                                                                       'J4': {'exact_length': 2,
                                                                              'item': {'kind': 'number'},
                                                                              'kind': 'array',
                                                                              'min_length': 1},
                                                                       'J5': {'exact_length': 2,
                                                                              'item': {'kind': 'number'},
                                                                              'kind': 'array',
                                                                              'min_length': 1},
                                                                       'J6': {'exact_length': 2,
                                                                              'item': {'kind': 'number'},
                                                                              'kind': 'array',
                                                                              'min_length': 1}}},
                                     'model_inputs': {'kind': 'mapping',
                                                      'min_entries': 1,
                                                      'value': {'kind': 'object',
                                                                'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                'required': {'bytes': {'kind': 'integer'}}}},
                                     'path_checks': {'exact_length': None,
                                                     'item': {'kind': 'object',
                                                              'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                              'required': {'cap_ratios': {'kind': 'object',
                                                                                          'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                          'required': {'J1': {'kind': 'number'},
                                                                                                       'J2': {'kind': 'number'},
                                                                                                       'J3': {'kind': 'number'},
                                                                                                       'J4': {'kind': 'number'},
                                                                                                       'J5': {'kind': 'number'},
                                                                                                       'J6': {'kind': 'number'},
                                                                                                       'KG1_pinion': {'kind': 'number'},
                                                                                                       'KG1_slide_A': {'kind': 'number'},
                                                                                                       'KG1_slide_B': {'kind': 'number'}}},
                                                                           'floor_clearance_m': {'kind': 'number'},
                                                                           'gravity_efforts': {'kind': 'object',
                                                                                               'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                               'required': {'J1': {'kind': 'number'},
                                                                                                            'J2': {'kind': 'number'},
                                                                                                            'J3': {'kind': 'number'},
                                                                                                            'J4': {'kind': 'number'},
                                                                                                            'J5': {'kind': 'number'},
                                                                                                            'J6': {'kind': 'number'},
                                                                                                            'KG1_pinion': {'kind': 'number'},
                                                                                                            'KG1_slide_A': {'kind': 'number'},
                                                                                                            'KG1_slide_B': {'kind': 'number'}}},
                                                                           'max_allowed_gravity_ratio': {'kind': 'number'},
                                                                           'max_gravity_ratio': {'kind': 'number'},
                                                                           'phase_index': {'kind': 'integer'},
                                                                           'q': {'kind': 'object',
                                                                                 'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                 'required': {'J1': {'kind': 'number'},
                                                                                              'J2': {'kind': 'number'},
                                                                                              'J3': {'kind': 'number'},
                                                                                              'J4': {'kind': 'number'},
                                                                                              'J5': {'kind': 'number'},
                                                                                              'J6': {'kind': 'number'},
                                                                                              'KG1_pinion': {'kind': 'number'},
                                                                                              'KG1_slide_A': {'kind': 'number'},
                                                                                              'KG1_slide_B': {'kind': 'number'}}},
                                                                           'step': {'kind': 'integer'},
                                                                           'tcp': {'exact_length': 3,
                                                                                   'item': {'kind': 'number'},
                                                                                   'kind': 'array',
                                                                                   'min_length': 1},
                                                                           'time_s': {'kind': 'number'}}},
                                                     'kind': 'array',
                                                     'min_length': 1},
                                     'planned_body_bounds': {'kind': 'object',
                                                             'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                             'required': {'max': {'exact_length': 3,
                                                                                  'item': {'kind': 'number'},
                                                                                  'kind': 'array',
                                                                                  'min_length': 1},
                                                                          'min': {'exact_length': 3,
                                                                                  'item': {'kind': 'number'},
                                                                                  'kind': 'array',
                                                                                  'min_length': 1}}},
                                     'program': {'kind': 'object',
                                                 'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                 'required': {'camera': {'kind': 'object',
                                                                         'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                         'required': {'eye': {'exact_length': 3,
                                                                                              'item': {'kind': 'number'},
                                                                                              'kind': 'array',
                                                                                              'min_length': 1},
                                                                                      'focal_length_mm': {'kind': 'number'},
                                                                                      'horizontal_aperture_mm': {'kind': 'number'},
                                                                                      'target': {'exact_length': 3,
                                                                                                 'item': {'kind': 'number'},
                                                                                                 'kind': 'array',
                                                                                                 'min_length': 1},
                                                                                      'vertical_aperture_mm': {'kind': 'number'}}},
                                                              'capture_count': {'kind': 'integer'},
                                                              'capture_stride': {'kind': 'integer'},
                                                              'drive': {'kind': 'object',
                                                                        'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                        'required': {'kd': {'kind': 'number'},
                                                                                     'kp': {'kind': 'number'}}},
                                                              'dt_s': {'kind': 'number'},
                                                              'duration_s': {'kind': 'number'},
                                                              'floor': {'kind': 'object',
                                                                        'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                        'required': {'scale': {'exact_length': 3,
                                                                                               'item': {'kind': 'number'},
                                                                                               'kind': 'array',
                                                                                               'min_length': 1},
                                                                                     'size': {'kind': 'number'},
                                                                                     'translation': {'exact_length': 3,
                                                                                                     'item': {'kind': 'number'},
                                                                                                     'kind': 'array',
                                                                                                     'min_length': 1}}},
                                                              'fps': {'kind': 'integer'},
                                                              'gravity_all': {'kind': 'boolean'},
                                                              'initial_opening_m': {'kind': 'number'},
                                                              'resolution': {'exact_length': 2,
                                                                             'item': {'kind': 'integer'},
                                                                             'kind': 'array',
                                                                             'min_length': 1},
                                                              'schema_version': {'kind': 'integer'},
                                                              'segments': {'exact_length': None,
                                                                           'item': {'kind': 'object',
                                                                                    'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                    'required': {'arm': {'kind': 'object',
                                                                                                         'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                                         'required': {'J1': {'kind': 'number'},
                                                                                                                      'J2': {'kind': 'number'},
                                                                                                                      'J3': {'kind': 'number'},
                                                                                                                      'J4': {'kind': 'number'},
                                                                                                                      'J5': {'kind': 'number'},
                                                                                                                      'J6': {'kind': 'number'}}},
                                                                                                 'checkpoint': {'kind': 'boolean'},
                                                                                                 'duration_s': {'kind': 'number'},
                                                                                                 'gravity': {'kind': 'boolean'},
                                                                                                 'opening_m': {'kind': 'number'}}},
                                                                           'kind': 'array',
                                                                           'min_length': 1},
                                                              'settling': {'kind': 'object',
                                                                           'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                           'required': {'arm_position_rad': {'kind': 'number'},
                                                                                        'arm_velocity_rad_s': {'kind': 'number'},
                                                                                        'jaw_position_m': {'kind': 'number'},
                                                                                        'jaw_velocity_m_s': {'kind': 'number'},
                                                                                        'pinion_position_rad': {'kind': 'number'},
                                                                                        'pinion_velocity_rad_s': {'kind': 'number'},
                                                                                        'window_s': {'kind': 'number'}}},
                                                              'steps': {'kind': 'integer'}}},
                                     'samples': {'exact_length': None,
                                                 'item': {'kind': 'object',
                                                          'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                          'required': {'cap_ratios': {'kind': 'object',
                                                                                      'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                      'required': {'J1': {'kind': 'number'},
                                                                                                   'J2': {'kind': 'number'},
                                                                                                   'J3': {'kind': 'number'},
                                                                                                   'J4': {'kind': 'number'},
                                                                                                   'J5': {'kind': 'number'},
                                                                                                   'J6': {'kind': 'number'},
                                                                                                   'KG1_pinion': {'kind': 'number'},
                                                                                                   'KG1_slide_A': {'kind': 'number'},
                                                                                                   'KG1_slide_B': {'kind': 'number'}}},
                                                                       'feasible': {'kind': 'boolean'},
                                                                       'floor_clearance_m': {'kind': 'number'},
                                                                       'gravity_efforts': {'kind': 'object',
                                                                                           'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                           'required': {'J1': {'kind': 'number'},
                                                                                                        'J2': {'kind': 'number'},
                                                                                                        'J3': {'kind': 'number'},
                                                                                                        'J4': {'kind': 'number'},
                                                                                                        'J5': {'kind': 'number'},
                                                                                                        'J6': {'kind': 'number'},
                                                                                                        'KG1_pinion': {'kind': 'number'},
                                                                                                        'KG1_slide_A': {'kind': 'number'},
                                                                                                        'KG1_slide_B': {'kind': 'number'}}},
                                                                       'index': {'kind': 'integer'},
                                                                       'max_gravity_ratio': {'kind': 'number'},
                                                                       'q': {'kind': 'object',
                                                                             'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                             'required': {'J1': {'kind': 'number'},
                                                                                          'J2': {'kind': 'number'},
                                                                                          'J3': {'kind': 'number'},
                                                                                          'J4': {'kind': 'number'},
                                                                                          'J5': {'kind': 'number'},
                                                                                          'J6': {'kind': 'number'},
                                                                                          'KG1_pinion': {'kind': 'number'},
                                                                                          'KG1_slide_A': {'kind': 'number'},
                                                                                          'KG1_slide_B': {'kind': 'number'}}},
                                                                       'tcp': {'exact_length': 3,
                                                                               'item': {'kind': 'number'},
                                                                               'kind': 'array',
                                                                               'min_length': 1}}},
                                                 'kind': 'array',
                                                 'min_length': 1},
                                     'schema_version': {'kind': 'integer'},
                                     'settings': {'kind': 'object',
                                                  'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                  'required': {'cloud_max_gravity_ratio': {'kind': 'number'},
                                                               'floor_clearance_m': {'kind': 'number'},
                                                               'gripper_opening_m': {'kind': 'number'},
                                                               'max_render_voxels': {'kind': 'integer'},
                                                               'sample_count': {'kind': 'integer'},
                                                               'seed': {'kind': 'integer'},
                                                               'transition_max_gravity_ratio': {'kind': 'number'},
                                                               'voxel_size_m': {'kind': 'number'}}},
                                     'stats': {'kind': 'object',
                                               'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                               'required': {'feasible_count': {'kind': 'integer'},
                                                            'initial_inside_conservative_cloud': {'kind': 'boolean'},
                                                            'initial_max_gravity_ratio': {'kind': 'number'},
                                                            'kinematic_bounds': {'kind': 'object',
                                                                                 'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                 'required': {'max': {'exact_length': 3,
                                                                                                      'item': {'kind': 'number'},
                                                                                                      'kind': 'array',
                                                                                                      'min_length': 1},
                                                                                              'min': {'exact_length': 3,
                                                                                                      'item': {'kind': 'number'},
                                                                                                      'kind': 'array',
                                                                                                      'min_length': 1}}},
                                                            'path_max_gravity_ratio': {'kind': 'number'},
                                                            'path_min_floor_clearance_m': {'kind': 'number'},
                                                            'peak_acceleration': {'kind': 'object',
                                                                                  'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                  'required': {'J1': {'kind': 'number'},
                                                                                               'J2': {'kind': 'number'},
                                                                                               'J3': {'kind': 'number'},
                                                                                               'J4': {'kind': 'number'},
                                                                                               'J5': {'kind': 'number'},
                                                                                               'J6': {'kind': 'number'},
                                                                                               'KG1_pinion': {'kind': 'number'},
                                                                                               'KG1_slide_A': {'kind': 'number'},
                                                                                               'KG1_slide_B': {'kind': 'number'}}},
                                                            'peak_velocity': {'kind': 'object',
                                                                              'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                              'required': {'J1': {'kind': 'number'},
                                                                                           'J2': {'kind': 'number'},
                                                                                           'J3': {'kind': 'number'},
                                                                                           'J4': {'kind': 'number'},
                                                                                           'J5': {'kind': 'number'},
                                                                                           'J6': {'kind': 'number'},
                                                                                           'KG1_pinion': {'kind': 'number'},
                                                                                           'KG1_slide_A': {'kind': 'number'},
                                                                                           'KG1_slide_B': {'kind': 'number'}}},
                                                            'post_raise_max_gravity_ratio': {'kind': 'number'},
                                                            'render_count': {'kind': 'integer'},
                                                            'sample_count': {'kind': 'integer'},
                                                            'voxel_count': {'kind': 'integer'}}},
                                     'waypoints': {'exact_length': None,
                                                   'item': {'kind': 'object',
                                                            'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                            'required': {'arm_degrees': {'exact_length': 6,
                                                                                         'item': {'kind': 'number'},
                                                                                         'kind': 'array',
                                                                                         'min_length': 1},
                                                                         'cap_ratios': {'kind': 'object',
                                                                                        'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                        'required': {'J1': {'kind': 'number'},
                                                                                                     'J2': {'kind': 'number'},
                                                                                                     'J3': {'kind': 'number'},
                                                                                                     'J4': {'kind': 'number'},
                                                                                                     'J5': {'kind': 'number'},
                                                                                                     'J6': {'kind': 'number'},
                                                                                                     'KG1_pinion': {'kind': 'number'},
                                                                                                     'KG1_slide_A': {'kind': 'number'},
                                                                                                     'KG1_slide_B': {'kind': 'number'}}},
                                                                         'floor_clearance_m': {'kind': 'number'},
                                                                         'gravity_efforts': {'kind': 'object',
                                                                                             'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                             'required': {'J1': {'kind': 'number'},
                                                                                                          'J2': {'kind': 'number'},
                                                                                                          'J3': {'kind': 'number'},
                                                                                                          'J4': {'kind': 'number'},
                                                                                                          'J5': {'kind': 'number'},
                                                                                                          'J6': {'kind': 'number'},
                                                                                                          'KG1_pinion': {'kind': 'number'},
                                                                                                          'KG1_slide_A': {'kind': 'number'},
                                                                                                          'KG1_slide_B': {'kind': 'number'}}},
                                                                         'index': {'kind': 'integer'},
                                                                         'max_gravity_ratio': {'kind': 'number'},
                                                                         'q': {'kind': 'object',
                                                                               'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                               'required': {'J1': {'kind': 'number'},
                                                                                            'J2': {'kind': 'number'},
                                                                                            'J3': {'kind': 'number'},
                                                                                            'J4': {'kind': 'number'},
                                                                                            'J5': {'kind': 'number'},
                                                                                            'J6': {'kind': 'number'},
                                                                                            'KG1_pinion': {'kind': 'number'},
                                                                                            'KG1_slide_A': {'kind': 'number'},
                                                                                            'KG1_slide_B': {'kind': 'number'}}},
                                                                         'tcp': {'exact_length': 3,
                                                                                 'item': {'kind': 'number'},
                                                                                 'kind': 'array',
                                                                                 'min_length': 1}}},
                                                   'kind': 'array',
                                                   'min_length': 1}}},
 'source/config.json': {'kind': 'object',
                        'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                        'required': {'deadline_unix': {'kind': 'integer'},
                                     'export_timeout_s': {'kind': 'number'},
                                     'floor': {'kind': 'object',
                                               'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                               'required': {'position': {'exact_length': 3,
                                                                         'item': {'kind': 'number'},
                                                                         'kind': 'array',
                                                                         'min_length': 1},
                                                            'scale': {'exact_length': 3,
                                                                      'item': {'kind': 'number'},
                                                                      'kind': 'array',
                                                                      'min_length': 1},
                                                            'size': {'kind': 'number'}}},
                                     'fps': {'kind': 'integer'},
                                     'hardware_approved': {'kind': 'boolean'},
                                     'height': {'kind': 'integer'},
                                     'minimum_launch_headroom_s': {'kind': 'number'},
                                     'motion_launch_headroom_s': {'kind': 'number'},
                                     'motion_timeout_s': {'kind': 'number'},
                                     'native_limits': {'kind': 'object',
                                                       'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                       'required': {'import': {'kind': 'integer'},
                                                                    'motion': {'kind': 'integer'},
                                                                    'render_smoke': {'kind': 'integer'}}},
                                     'offline_only': {'kind': 'boolean'},
                                     'physical_calibration': {'kind': 'boolean'},
                                     'recovery_total_s': {'kind': 'number'},
                                     'schema_version': {'kind': 'integer'},
                                     'sdk': {'kind': 'object',
                                             'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                             'required': {'calibration_approved': {'kind': 'boolean'},
                                                          'cap_Nm': {'exact_length': 6,
                                                                     'item': {'kind': 'number'},
                                                                     'kind': 'array',
                                                                     'min_length': 1},
                                                          'gravity': {'exact_length': 3,
                                                                      'item': {'kind': 'number'},
                                                                      'kind': 'array',
                                                                      'min_length': 1},
                                                          'hardware_approved': {'kind': 'boolean'},
                                                          'rate_hz': {'kind': 'number'},
                                                          'schema_version': {'kind': 'integer'},
                                                          'stage_limits': {'kind': 'object',
                                                                           'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                           'required': {'robot_connection': {'kind': 'integer'},
                                                                                        'sdk_preflight': {'kind': 'integer'}}},
                                                          'steps': {'kind': 'integer'},
                                                          'timeout_s': {'kind': 'number'}}},
                                     'timeout_s': {'kind': 'number'},
                                     'width': {'kind': 'integer'}}},
 'source/program.json': {'kind': 'object',
                         'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                         'required': {'camera': {'kind': 'object',
                                                 'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                 'required': {'eye': {'exact_length': 3,
                                                                      'item': {'kind': 'number'},
                                                                      'kind': 'array',
                                                                      'min_length': 1},
                                                              'focal_length_mm': {'kind': 'number'},
                                                              'horizontal_aperture_mm': {'kind': 'number'},
                                                              'target': {'exact_length': 3,
                                                                         'item': {'kind': 'number'},
                                                                         'kind': 'array',
                                                                         'min_length': 1},
                                                              'vertical_aperture_mm': {'kind': 'number'}}},
                                      'capture_count': {'kind': 'integer'},
                                      'capture_stride': {'kind': 'integer'},
                                      'drive': {'kind': 'object',
                                                'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                'required': {'kd': {'kind': 'number'},
                                                             'kp': {'kind': 'number'}}},
                                      'dt_s': {'kind': 'number'},
                                      'duration_s': {'kind': 'number'},
                                      'floor': {'kind': 'object',
                                                'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                'required': {'scale': {'exact_length': 3,
                                                                       'item': {'kind': 'number'},
                                                                       'kind': 'array',
                                                                       'min_length': 1},
                                                             'size': {'kind': 'number'},
                                                             'translation': {'exact_length': 3,
                                                                             'item': {'kind': 'number'},
                                                                             'kind': 'array',
                                                                             'min_length': 1}}},
                                      'fps': {'kind': 'integer'},
                                      'gravity_all': {'kind': 'boolean'},
                                      'initial_opening_m': {'kind': 'number'},
                                      'resolution': {'exact_length': 2,
                                                     'item': {'kind': 'integer'},
                                                     'kind': 'array',
                                                     'min_length': 1},
                                      'schema_version': {'kind': 'integer'},
                                      'segments': {'exact_length': None,
                                                   'item': {'kind': 'object',
                                                            'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                            'required': {'arm': {'kind': 'object',
                                                                                 'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                                                 'required': {'J1': {'kind': 'number'},
                                                                                              'J2': {'kind': 'number'},
                                                                                              'J3': {'kind': 'number'},
                                                                                              'J4': {'kind': 'number'},
                                                                                              'J5': {'kind': 'number'},
                                                                                              'J6': {'kind': 'number'}}},
                                                                         'checkpoint': {'kind': 'boolean'},
                                                                         'duration_s': {'kind': 'number'},
                                                                         'gravity': {'kind': 'boolean'},
                                                                         'opening_m': {'kind': 'number'}}},
                                                   'kind': 'array',
                                                   'min_length': 1},
                                      'settling': {'kind': 'object',
                                                   'other': 'opaque_metadata_without_numeric_or_logical_leaves',
                                                   'required': {'arm_position_rad': {'kind': 'number'},
                                                                'arm_velocity_rad_s': {'kind': 'number'},
                                                                'jaw_position_m': {'kind': 'number'},
                                                                'jaw_velocity_m_s': {'kind': 'number'},
                                                                'pinion_position_rad': {'kind': 'number'},
                                                                'pinion_velocity_rad_s': {'kind': 'number'},
                                                                'window_s': {'kind': 'number'}}},
                                      'steps': {'kind': 'integer'}}}}

SOURCE_NAMES = frozenset(('bootstrap.py config.json driver.py launch.ps1 sdk.py test_host.py '
    'validate.py winjob.py README.md balance.py capture.py init_boundary.py program.json '
    'recovery.py reference.py root_binding.py scene.py test_scene.py torque.py workspace.py '
    'decision_schema.py').split())
MODEL_NAMES = frozenset(('asset-ledger.json manifest.json provenance.json README.md robot_arm.urdf '
    'meshes/Base.stl meshes/KG1_A.stl meshes/KG1_B.stl meshes/KG1_R.stl meshes/KG1.stl '
    'meshes/Link1.stl meshes/Link2.stl meshes/Link3.stl meshes/Link4.stl meshes/Link5.stl meshes/Link6.stl').split())
REF_NAMES = frozenset(('kernel.py numeric.py policy.py observer.py extract.py physics_reference.py '
    'prefix-seal.json model-submission.json workspace.json sampling-oracle.py torque_api.py').split())
INPUT_NAMES = frozenset({'source/' + n for n in SOURCE_NAMES} |
    {'model/' + n for n in MODEL_NAMES} | {'ref/' + n for n in REF_NAMES})
STL_NAMES = frozenset('model/' + n for n in MODEL_NAMES if n.endswith('.stl'))
SCOPE = 'TYPED_DECISION_INPUTS_NOT_NATIVE_AUTHORITY'
_DECIMAL = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')


def _require(condition, message):
    if not condition:
        raise ValueError('decision policy: ' + message)


def _seal(value):
    if type(value) is dict:
        return MappingProxyType({key: _seal(child) for key, child in value.items()})
    if type(value) is list:
        return tuple(_seal(child) for child in value)
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_document(raw, declaration, name):
    def pairs(entries):
        obj = {}
        for key, value in entries:
            _require(key not in obj, name + ': duplicate object key')
            obj[key] = value
        return obj

    def constant(token):
        raise ValueError('decision policy: nonfinite JSON constant ' + token)

    def number(token):
        value = float(token)
        _require(math.isfinite(value), name + ': nonfinite JSON number')
        return value

    document = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_float=number, parse_constant=constant)
    actual = {}

    def inventory(item, path):
        if type(item) in (int, float, bool):
            _require(type(item) is not float or math.isfinite(item), name + ': finite leaf')
            actual[path] = 'boolean' if type(item) is bool else 'numeric'
        elif type(item) is dict:
            for key, child in item.items():
                inventory(child, path + (key,))
        elif type(item) is list:
            for index, child in enumerate(item):
                inventory(child, path + (index,))
        else:
            _require(item is None or type(item) is str, name + ': JSON leaf type')

    inventory(document, ())
    covered = {}
    reached = set()

    def interpret(item, role, path):
        kind = role['kind']
        _require(path not in reached, name + ': repeated declaration path')
        reached.add(path)
        label = name + ':' + repr(path)
        if kind in ('number', 'integer', 'boolean'):
            valid = (type(item) in (int, float) and
                     (type(item) is int or math.isfinite(item))) if kind == 'number' else (
                         type(item) is int if kind == 'integer' else type(item) is bool)
            _require(valid, label + ': required ' + kind)
            covered[path] = 'boolean' if kind == 'boolean' else 'numeric'
        elif kind == 'object':
            _require(type(item) is dict, label + ': required object')
            required = role['required']
            _require(set(required) <= set(item), label + ': missing required fields')
            for key, child in required.items():
                interpret(item[key], child, path + (key,))
        elif kind == 'array':
            _require(type(item) is list and len(item) >= role['min_length'] and
                     (role['exact_length'] is None or len(item) == role['exact_length']),
                     label + ': required array cardinality')
            for index, child in enumerate(item):
                interpret(child, role['item'], path + (index,))
        elif kind == 'mapping':
            _require(type(item) is dict and len(item) >= role['min_entries'],
                     label + ': required mapping cardinality')
            for key, child in item.items():
                interpret(child, role['value'], path + (key,))
        else:
            raise ValueError('decision policy: unknown pinned IR role')

    interpret(document, declaration, ())
    _require(actual == covered, name + ': undeclared or uncovered numeric/logical leaf')
    return sum(kind == 'numeric' for kind in covered.values()), sum(
        kind == 'boolean' for kind in covered.values())


def _decimal_components(text, arity, location):
    _require(type(text) is str, location + ': missing numeric attribute')
    pieces = text.split()
    _require(len(pieces) == arity, location + ': numeric arity')
    for piece in pieces:
        _require(_DECIMAL.fullmatch(piece) is not None, location + ': decimal grammar')
        _require(math.isfinite(float(piece)), location + ': finite decimal')
    return arity


_LINKS = frozenset(['Base', 'KG1', 'KG1_A', 'KG1_B', 'KG1_R', 'tool0'] +
                   ['Link' + str(i) for i in range(1, 7)])
_JOINTS = MappingProxyType(dict({('J' + str(i)): 'revolute' for i in range(1, 7)},
    KG1_mount='fixed', tool0_mount='fixed', KG1_slide_A='prismatic',
    KG1_slide_B='prismatic', KG1_pinion='revolute'))
# Path-sensitive declarations: exact attributes and exact child multiplicities.
_XML = {
    'robot': ({'name': 0}, {'link': (12, 12), 'joint': (11, 11)}),
    'robot/link': ({'name': 0}, {}),
    'robot/link/inertial': ({}, {'origin': (1, 1), 'mass': (1, 1), 'inertia': (1, 1)}),
    'robot/link/inertial/mass': ({'value': 1}, {}),
    'robot/link/inertial/inertia': ({k: 1 for k in ('ixx', 'iyy', 'izz', 'ixy', 'ixz', 'iyz')}, {}),
    'robot/link/visual': ({}, {'origin': (1, 1), 'geometry': (1, 1), 'material': (1, 1)}),
    'robot/link/visual/geometry': ({}, {'mesh': (1, 1)}),
    'robot/link/visual/geometry/mesh': ({'filename': 0, 'scale': 3}, {}),
    'robot/link/visual/material': ({'name': 0}, {'color': (0, 1)}),
    'robot/link/visual/material/color': ({'rgba': 4}, {}),
    'robot/link/collision': ({}, {'origin': (1, 1), 'geometry': (1, 1)}),
    'robot/link/collision/geometry': ({}, {'box': (1, 1)}),
    'robot/link/collision/geometry/box': ({'size': 3}, {}),
    'robot/joint': ({'name': 0, 'type': 0}, {}),
    'robot/joint/parent': ({'link': 0}, {}),
    'robot/joint/child': ({'link': 0}, {}),
    'robot/joint/axis': ({'xyz': 3}, {}),
    'robot/joint/limit': ({k: 1 for k in ('lower', 'upper', 'effort', 'velocity')}, {}),
    'robot/joint/dynamics': ({'damping': 1, 'friction': 1}, {}),
    'robot/joint/mimic': ({'joint': 0, 'multiplier': 1, 'offset': 1}, {}),
}
for _origin_path in ('robot/link/inertial/origin', 'robot/link/visual/origin',
                     'robot/link/collision/origin', 'robot/joint/origin'):
    _XML[_origin_path] = ({'xyz': 3, 'rpy': 3}, {})
_XML = _seal(_XML)


def _urdf_document(raw):
    text = raw.decode('utf-8')
    # Strip XML comments before testing declaration boundaries; ET also ignores comments.
    declarations = re.sub(r'<!--[\s\S]*?-->', '', text)
    _require(re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', declarations, re.IGNORECASE) is None,
             'URDF forbidden XML declaration')
    root = ET.fromstring(text)
    _require(root.tag == 'robot', 'URDF root')
    links = [node.attrib.get('name') for node in root if node.tag == 'link']
    joints = [(node.attrib.get('name'), node.attrib.get('type')) for node in root if node.tag == 'joint']
    _require(len(links) == len(_LINKS) and set(links) == _LINKS, 'URDF fixed link profile')
    _require(len(joints) == len(_JOINTS) and dict(joints) == dict(_JOINTS), 'URDF fixed joint profile')

    def visit(node, path):
        _require(path in _XML, 'URDF undeclared element ' + path)
        attrs, child_rules = _XML[path]
        _require(set(node.attrib) == set(attrs), 'URDF exact attributes ' + path)
        _require(node.text is None or not node.text.strip(), 'URDF unexpected element text')
        total = 0
        for key, arity in attrs.items():
            if arity:
                total += _decimal_components(node.attrib[key], arity, path + '@' + key)
            else:
                _require(type(node.attrib[key]) is str and bool(node.attrib[key].strip()),
                         'URDF required text attribute')
        if path == 'robot/link':
            child_rules = {} if node.attrib['name'] == 'tool0' else {
                'inertial': (1, 1), 'visual': (1, 1), 'collision': (1, 1)}
        elif path == 'robot/joint':
            child_rules = {'parent': (1, 1), 'child': (1, 1), 'origin': (1, 1)}
            if node.attrib['type'] != 'fixed':
                child_rules.update(axis=(1, 1), limit=(1, 1), dynamics=(1, 1))
            if node.attrib['name'] in ('KG1_slide_B', 'KG1_pinion'):
                child_rules['mimic'] = (1, 1)
        counts = Counter(child.tag for child in node)
        _require(set(counts) <= set(child_rules), 'URDF undeclared child ' + path)
        for tag, (lower, upper) in child_rules.items():
            _require(lower <= counts[tag] <= upper, 'URDF child cardinality ' + path + '/' + tag)
        for child in node:
            _require(child.tail is None or not child.tail.strip(), 'URDF unexpected tail text')
            total += visit(child, path + '/' + child.tag)
        return total

    return visit(root, 'robot'), 0


def _stl_document(raw):
    # Binary length is authoritative even when its opaque header starts with solid.
    if len(raw) >= 84:
        triangles = struct.unpack_from('<I', raw, 80)[0]
        if len(raw) == 84 + 50 * triangles:
            for record in struct.iter_unpack('<12fH', memoryview(raw)[84:]):
                _require(all(math.isfinite(x) for x in record[:12]), 'STL finite binary component')
                _require(type(record[12]) is int and 0 <= record[12] <= 65535, 'STL binary attribute')
            return 'STL_BINARY', 1 + 13 * triangles, 0
    text = raw.decode('ascii')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    _require(len(lines) >= 2 and re.fullmatch(r'solid(?:\s+.*)?', lines[0]) is not None,
             'STL ASCII solid boundary')
    _require(re.fullmatch(r'endsolid(?:\s+.*)?', lines[-1]) is not None,
             'STL ASCII end boundary')
    body = ' '.join(lines[1:-1]).split()
    _require(len(body) % 21 == 0, 'STL ASCII complete facet records')
    components = 0
    for base in range(0, len(body), 21):
        facet = body[base:base + 21]
        _require(facet[:2] == ['facet', 'normal'] and facet[5:7] == ['outer', 'loop'] and
                 facet[19:] == ['endloop', 'endfacet'], 'STL ASCII facet grammar')
        components += _decimal_components(' '.join(facet[2:5]), 3, 'STL normal')
        for start in (7, 11, 15):
            _require(facet[start] == 'vertex', 'STL ASCII vertex grammar')
            components += _decimal_components(' '.join(facet[start + 1:start + 4]), 3, 'STL vertex')
    return 'STL_ASCII', components, 0


def validate_decision_inputs(bundle48):
    """Return fresh all-file coverage after checking every declared decision scalar."""
    _require(type(bundle48) in (dict, MappingProxyType) and set(bundle48) == INPUT_NAMES,
             'closed input48 names')
    private = {}
    for name, raw in bundle48.items():
        _require(type(name) is str and type(raw) is bytes and len(raw) > 0,
                 'exact nonempty named input bytes')
        private[name] = memoryview(raw).tobytes()
    bundle = MappingProxyType(private)
    own = globals().get('__source_bytes__')
    _require(type(own) is bytes and own == bundle['source/decision_schema.py'],
             'actual executed policy source binding')
    files = {}
    for name in sorted(INPUT_NAMES):
        if name in JSON_ROLES:
            numeric, logical = _json_document(bundle[name], JSON_ROLES[name], name)
            kind = 'JSON'
        elif name == 'model/robot_arm.urdf':
            numeric, logical = _urdf_document(bundle[name])
            kind = 'URDF'
        elif name in STL_NAMES:
            kind, numeric, logical = _stl_document(bundle[name])
        else:
            kind, numeric, logical = 'OPAQUE', 0, 0
        files[name] = {'kind': kind, 'numeric_components': numeric, 'logical_values': logical}
    pins = {name: {'sha256': _sha(raw), 'bytes': len(raw)} for name, raw in sorted(bundle.items())}
    totals = {'numeric_components': sum(row['numeric_components'] for row in files.values()),
              'logical_values': sum(row['logical_values'] for row in files.values()),
              'typed_files': sum(row['kind'] != 'OPAQUE' for row in files.values()),
              'opaque_files': sum(row['kind'] == 'OPAQUE' for row in files.values())}
    _require(totals['typed_files'] == 20 and totals['opaque_files'] == 28, 'closed format census')
    return {'schema_version': 1, 'unit': '113', 'scope': SCOPE, 'policy_sha256': _sha(own),
            'inputs_sha256': _sha(_canonical(pins)), 'files': files, 'totals': totals}


JSON_ROLES = _seal(JSON_ROLES)
