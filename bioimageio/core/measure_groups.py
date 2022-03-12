from __future__ import annotations

import collections
import warnings
from collections import defaultdict
from itertools import product
from typing import (
    DefaultDict,
    Dict,
    Hashable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

import numpy
import xarray as xr

from bioimageio.core.statistical_measures import Mean, Measure, Percentile, Std, Var
from .utils import DatasetMode, PER_DATASET, PER_SAMPLE, SampleMode, TensorName

try:
    import crick
except ImportError:
    crick = None

MeasureValue = xr.DataArray


class SampleMeasureGroup:
    """group of measures for more efficient computation of multiple measures per sample"""

    def compute(self, sample: Dict[TensorName, xr.DataArray]) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        raise NotImplementedError


class DatasetMeasureGroup:
    """group of measures for more efficient computation of multiple measures per dataset"""

    def reset(self) -> None:
        raise NotImplementedError

    def update_with_sample(self, sample: Dict[TensorName, xr.DataArray]) -> None:
        raise NotImplementedError

    def finalize(self) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        raise NotImplementedError


class MeasureGroup(SampleMeasureGroup, DatasetMeasureGroup):
    pass


class DatasetMean(DatasetMeasureGroup):
    n: int
    mean: Optional[xr.DataArray]

    def __init__(self, tensor_name: TensorName, axes: Optional[Tuple[int]]):
        self.axes: Optional[Tuple[str]] = axes
        self.tensor_name = tensor_name
        self.reset()

    def reset(self):
        self.n = 0
        self.mean = None

    def update_with_sample(self, sample: Dict[TensorName, xr.DataArray]):
        tensor = sample[self.tensor_name].astype(numpy.float64, copy=False)
        mean_b = tensor.mean(dim=self.axes)
        assert mean_b.dtype == numpy.float64
        n_b = numpy.prod(tensor.shape) / numpy.prod(mean_b.shape)  # reduced voxel count
        if self.n == 0:
            assert self.mean is None
            self.n = n_b
            self.mean = mean_b
        else:
            n_a = self.n
            mean_a = self.mean
            self.n = n = n_a + n_b
            self.mean = (n_a * mean_a + n_b * mean_b) / n
            assert self.mean.dtype == numpy.float64

    def finalize(self) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        return {self.tensor_name: {Mean(axes=self.axes): self.mean}}


class MeanVarStd(MeasureGroup):
    n: int
    mean: Optional[xr.DataArray]
    m2: Optional[xr.DataArray]

    def __init__(self, tensor_name: TensorName, axes: Optional[Tuple[int]]):
        self.axes: Optional[Tuple[str]] = axes
        self.tensor_name = tensor_name
        self.reset()

    def compute(self, sample: Dict[TensorName, xr.DataArray]) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        tensor = sample[self.tensor_name]
        mean = tensor.mean(dim=self.axes)
        c = tensor - mean
        var = xr.dot(c, c, dims=self.axes) / tensor.size
        std = xr.ufuncs.sqrt(var)
        return {self.tensor_name: {Mean(axes=self.axes): mean, Var(axes=self.axes): var, Std(axes=self.axes): std}}

    def reset(self):
        self.n = 0
        self.mean = None
        self.m2 = None

    def update_with_sample(self, sample: Dict[TensorName, xr.DataArray]):
        tensor = sample[self.tensor_name].astype(numpy.float64, copy=False)
        mean_b = tensor.mean(dim=self.axes)
        assert mean_b.dtype == numpy.float64
        n_b = numpy.prod(tensor.shape) / numpy.prod(mean_b.shape)  # reduced voxel count
        m2_b = ((tensor - mean_b) ** 2).sum(dim=self.axes)
        assert m2_b.dtype == numpy.float64
        if self.n == 0:
            assert self.mean is None
            assert self.m2 is None
            self.n = n_b
            self.mean = mean_b
            self.m2 = m2_b
        else:
            n_a = self.n
            mean_a = self.mean
            m2_a = self.m2
            self.n = n = n_a + n_b
            self.mean = (n_a * mean_a + n_b * mean_b) / n
            assert self.mean.dtype == numpy.float64
            d = mean_b - mean_a
            self.m2 = m2_a + m2_b + d ** 2 * n_a * n_b / n
            assert self.m2.dtype == numpy.float64

    def finalize(self) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        var = self.m2 / self.n
        return {
            self.tensor_name: {
                Mean(axes=self.axes): self.mean,
                Var(axes=self.axes): var,
                Std(axes=self.axes): xr.ufuncs.sqrt(var),
            }
        }


class SamplePercentiles(SampleMeasureGroup):
    def __init__(self, tensor_name: TensorName, axes: Optional[Tuple[str]], ns: Sequence[float]):
        assert all(0 <= n <= 100 for n in ns)
        self.ns = ns
        self.qs = [n / 100 for n in ns]
        self.axes = axes
        self.tensor_name = tensor_name

    def compute(self, sample: Dict[TensorName, xr.DataArray]) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        tensor = sample[self.tensor_name]
        ps = tensor.quantile(self.qs, dim=self.axes)
        return {self.tensor_name: {Percentile(n=n, axes=self.axes): p for n, p in zip(self.ns, ps)}}


class MeanPercentiles(DatasetMeasureGroup):
    count: int
    estimates: Optional[xr.DataArray]

    def __init__(self, tensor_name: TensorName, axes: Optional[Tuple[str]], ns: Sequence[float]):
        assert all(0 <= n <= 100 for n in ns)
        self.ns = ns
        self.qs = [n / 100 for n in ns]
        self.axes = axes
        self.tensor_name = tensor_name
        self.reset()

    def reset(self):
        self.count = 0
        self.estimates = None

    def update_with_sample(self, sample: Dict[TensorName, xr.DataArray]):
        tensor = sample[self.tensor_name]
        sample_estimates = tensor.quantile(self.qs, dim=self.axes).astype(numpy.float64, copy=False)

        n = numpy.prod(tensor.shape) / numpy.prod(sample_estimates.shape[1:])  # reduced voxel count

        if self.count == 0:
            self.estimates = sample_estimates
        else:
            self.estimates = (self.count * self.estimates + n * sample_estimates) / (self.count + n)
            assert self.estimates.dtype == numpy.float64

        self.count += n

    def finalize(self) -> Dict[Percentile, MeasureValue]:
        warnings.warn(f"Computed dataset percentiles naively by averaging percentiles of samples.")
        assert self.estimates is not None
        return {Percentile(n=n, axes=self.axes): e for n, e in zip(self.ns, self.estimates)}


class CrickPercentiles(DatasetMeasureGroup):
    digest: Optional[List["crick.TDigest"]]
    dims: Optional[Tuple[Hashable, ...]]
    indices: Optional[Iterator[Tuple[int, ...]]]
    shape: Optional[Tuple[int, ...]]

    def __init__(self, tensor_name: TensorName, axes: Optional[Tuple[str]], ns: Sequence[float]):
        assert all(0 <= n <= 100 for n in ns)
        assert axes is None or "_percentiles" not in axes
        warnings.warn(f"Computing dataset percentiles with experimental 'crick' library.")
        self.ns = ns
        self.qs = [n / 100 for n in ns]
        self.axes = axes
        self.tensor_name = tensor_name
        self.reset()

    def reset(self):
        self.digest = None
        self.dims = None
        self.indices = None
        self.shape = None

    def _initialize(self, tensor_sizes: Mapping[Hashable, int]):
        out_sizes = collections.OrderedDict(_percentiles=len(self.ns))
        if self.axes is not None:
            for d, s in tensor_sizes.items():
                if d not in self.axes:
                    out_sizes[d] = s

        self.dims, self.shape = zip(*out_sizes.items())
        self.digest = [crick.TDigest() for _ in range(int(numpy.prod(self.shape[1:])))]
        self.indices = product(*map(range, self.shape[1:]))

    def update_with_sample(self, sample: Dict[TensorName, xr.DataArray]):
        tensor = sample[self.tensor_name]
        assert "_percentiles" not in tensor.dims
        if self.digest is None:
            self._initialize(tensor.sizes)
            assert self.digest is not None

        for i, idx in enumerate(self.indices):
            self.digest[i].update(tensor.isel(dict(zip(self.dims[1:], idx))))

    def finalize(self) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        vs = numpy.asarray([[d.quantile(q) for d in self.digest] for q in self.qs]).reshape(self.shape)
        return {
            self.tensor_name: {
                Percentile(n=n, axes=self.axes): xr.DataArray(v, dims=self.dims[1:]) for n, v in zip(self.ns, vs)
            }
        }


if crick is None:
    DatasetPercentileGroup: Union[Type[MeanPercentiles], Type[CrickPercentiles]] = MeanPercentiles
else:
    DatasetPercentileGroup = CrickPercentiles


class SingleMeasureAsGroup(SampleMeasureGroup):
    """wrapper for measures to match interface of SampleMeasureGroup"""

    def __init__(self, tensor_name: TensorName, measure: Measure):
        self.tensor_name = tensor_name
        self.measure = measure

    def compute(self, sample: Dict[TensorName, xr.DataArray]) -> Dict[TensorName, Dict[Measure, MeasureValue]]:
        return {self.tensor_name: {self.measure: self.measure.compute(sample[self.tensor_name])}}


def get_measure_groups(
    measures: Dict[TensorName, Set[Measure]], mode: Literal[SampleMode, DatasetMode]
) -> List[Union[SampleMeasureGroup, DatasetMeasureGroup]]:
    """find a list of MeasureGroups to compute measures efficiently"""

    measure_groups = []
    means: Set[Tuple[TensorName, Mean]] = set()
    mean_var_std_groups: Set[Tuple[TensorName, Optional[Tuple[str, ...]]]] = set()
    percentile_groups: DefaultDict[Tuple[TensorName, Optional[Tuple[str, ...]]], List[float]] = defaultdict(list)
    for tn, ms in measures.items():
        for m in ms:
            if isinstance(m, Mean):
                means.add((tn, m))
            elif isinstance(m, (Var, Std)):
                mean_var_std_groups.add((tn, m.axes))
            elif isinstance(m, Percentile):
                percentile_groups[(tn, m.axes)].append(m.n)
            elif mode == PER_SAMPLE:
                measure_groups.append(SingleMeasureAsGroup(tensor_name=tn, measure=m))
            else:
                raise NotImplementedError(f"Computing statistics for {m} {mode} not yet implemented")

    # add all mean measures that are not included in a mean/var/std group
    for (tn, m) in means:
        if (tn, m.axes) not in mean_var_std_groups:
            # compute only mean
            if mode == PER_SAMPLE:
                measure_groups.append(SingleMeasureAsGroup(tensor_name=tn, measure=m))
            elif mode == PER_DATASET:
                measure_groups.append(DatasetMean(tensor_name=tn, axes=m.axes))
            else:
                raise NotImplementedError(mode)

    for (tn, axes) in mean_var_std_groups:
        measure_groups.append(MeanVarStd(tensor_name=tn, axes=axes))

    for (tn, axes), ns in percentile_groups.items():
        if mode == PER_SAMPLE:
            measure_groups.append(SamplePercentiles(tensor_name=tn, axes=axes, ns=ns))
        elif mode == PER_DATASET:
            measure_groups.append(DatasetPercentileGroup(tensor_name=tn, axes=axes, ns=ns))
        else:
            raise NotImplementedError(mode)

    return measure_groups
