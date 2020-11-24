from pathlib import Path

import numpy

from pybio.sklearn.training.classic_fit import classic_fit
from pybio.spec import load_spec


def test_RandomForestClassifier():
    spec_path = Path(__file__).parent / "../../../specs/models/sklearn/RandomForestClassifier.model.yaml"
    pybio_model = load_spec(spec_path.as_uri())
    model = classic_fit(pybio_model)

    ipt = [numpy.arange(24).reshape((2, 3, 4))]
    out = model(ipt)
    assert len(out) == 1
    assert out[0].shape == ipt[0].shape
