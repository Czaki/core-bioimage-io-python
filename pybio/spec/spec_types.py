from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Callable, Any, Dict, NewType, Tuple, Union, Type, NamedTuple


class MagicTensorsValue(Enum):
    any = "any"
    same = "same"
    dynamic = "dynamic"


class MagicShapeValue(Enum):
    any = "any"
    dynamic = "dynamic"


# Types for non-nested fields
Axes = NewType("Axes", str)
Dependencies = NewType("Dependencies", Path)

# Types for schema
@dataclass
class CiteEntry:
    text: str
    doi: Optional[str]
    url: Optional[str]


@dataclass
class MinimalYAML:
    name: str
    format_version: str
    description: str
    cite: List[CiteEntry]
    authors: List[str]
    documentation: Path
    tags: List[str]

    language: str
    framework: Optional[str]
    source: Callable
    required_kwargs: List[str]
    optional_kwargs: Dict[str, Any]

    test_input: Optional[Path]
    test_output: Optional[Path]
    thumbnail: Optional[Path]


@dataclass
class InputShape:
    min: List[float]
    step: List[float]

    def __len__(self):
        return len(self.min)


@dataclass
class OutputShape:
    reference_input: Optional[str]
    scale: List[float]
    offset: List[int]

    def __len__(self):
        return len(self.scale)


@dataclass
class Array:
    name: str
    axes: Optional[Axes]
    data_type: str
    data_range: Tuple[float, float]


@dataclass
class InputArray(Array):
    shape: Union[Tuple[int, ...], MagicShapeValue, InputShape]


@dataclass
class OutputArray(Array):
    shape: Union[Tuple[int, ...], MagicShapeValue, OutputShape]
    halo: List[int]


@dataclass
class WithInputs:
    inputs: Union[MagicTensorsValue, List[InputArray]]


@dataclass
class WithOutputs:
    outputs: Union[MagicTensorsValue, List[OutputArray]]


@dataclass
class Transformation(MinimalYAML, WithInputs, WithOutputs):
    dependencies: Dependencies


@dataclass
class BaseSpec:
    spec: MinimalYAML
    kwargs: Dict[str, Any]

    def get_instance(self, **kwargs) -> Any:
        joined_kwargs = dict(self.spec.optional_kwargs)
        joined_kwargs.update(self.kwargs)
        joined_kwargs.update(kwargs)
        return self.spec.source(**joined_kwargs)


@dataclass
class TransformationSpec(BaseSpec):
    spec: Transformation


@dataclass
class Weights:
    source: str
    hash: Dict[str, str]


@dataclass
class Prediction:
    weights: Weights
    dependencies: Optional[Dependencies]
    preprocess: Optional[List[TransformationSpec]]
    postprocess: Optional[List[TransformationSpec]]


@dataclass
class Reader(MinimalYAML, WithOutputs):
    dependencies: Optional[Dependencies]


@dataclass
class ReaderSpec(BaseSpec):
    spec: Reader


@dataclass
class Sampler(MinimalYAML, WithOutputs):
    dependencies: Optional[Dependencies]


@dataclass
class SamplerSpec(BaseSpec):
    spec = Sampler


@dataclass
class Optimizer:
    source: Callable
    required_kwargs: List[str]
    optional_kwargs: Dict[str, Any]

    def get_instance(self, parameters, **kwargs) -> Any:
        joined_kwargs = dict(self.optional_kwargs)
        joined_kwargs.update(kwargs)
        return self.source(parameters, **joined_kwargs)


@dataclass
class Setup:
    reader: ReaderSpec
    sampler: SamplerSpec
    preprocess: Optional[List[TransformationSpec]]
    loss: List[TransformationSpec]
    optimizer: Optimizer


@dataclass
class Training:
    setup: Setup
    source: Callable
    required_kwargs: List[str]
    optional_kwargs: Dict[str, Any]
    dependencies: Dependencies
    description: Optional[str]


@dataclass
class Model(MinimalYAML, WithInputs, WithOutputs):
    prediction: Prediction
    training: Optional[Training]


@dataclass
class ModelSpec(BaseSpec):
    spec: Model

    def train(self, **kwargs) -> Any:
        complete_kwargs = dict(self.spec.training.optional_kwargs)
        complete_kwargs.update(kwargs)

        mspec = "model_spec"
        if mspec not in complete_kwargs and mspec in self.spec.training.required_kwargs:
            complete_kwargs[mspec] = self

        return self.spec.training.source(**complete_kwargs)
