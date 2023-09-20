'''run configs to loop over - will take all combinations of the below lists - grows combinatorially!!'''

batch_config = {
    # loop-overable (must be a list)
    'cluster_size': [[10, 10, 10]],
    'temperature': [100, 200],
    'structure_identifier': ["NICOAM16", "NICOAM17"], #, "NICOAM17"],
    'defect_rate': [0, 0.2],
    'gap_rate': [0],
    'scramble_rate': [0],
    'seed': [1],
    'damping': [str(100.0)],
    'max_sphere_radius': [10, 15],

    # static items - DO NOT SET AS LIST
    'cluster_type': 'spherical',
    'run_time': int(1e4),
    'box_type': 'p',
    'integrator': 'nosehoover',
    'print_steps': int(1e2),
    'min_inter_cluster_distance': 1000,
    'bulk_crystal': False,
    'machine': 'cluster',
    'run_name': 'dev10',
}