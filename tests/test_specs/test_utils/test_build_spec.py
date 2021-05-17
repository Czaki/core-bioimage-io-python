import os
from bioimageio.spec import schema
from bioimageio.spec.utils import yaml


def test_build_spec_torch(rf_config_path):
    from bioimageio.spec.utils.build_spec import build_spec
    source = yaml.load(rf_config_path)

    root = rf_config_path.parents[0]

    weight_path = os.path.join(root, source['weights']['pickle']['source'])
    assert os.path.exists(weight_path), weight_path
    test_inputs = [os.path.join(root, pp) for pp in source['test_inputs']]
    test_outputs = [os.path.join(root, pp) for pp in source['test_outputs']]

    raw_model = build_spec(
        source=source['source'],
        model_kwargs=source['kwargs'],
        weight_uri=weight_path,
        test_inputs=test_inputs,
        test_outputs=test_outputs,
        name=source['name'],
        description=source['description'],
        authors=source['authors'],
        tags=source['tags'],
        license=source['license'],
        documentation=source['documentation'],
        covers=source['covers'],
        dependencies=source['dependencies'],
        weight_type='pickle'
    )

    # TODO fix this
    serialized = schema.Model().dump(raw_model)
    print(type(serialized))
