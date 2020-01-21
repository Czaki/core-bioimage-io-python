from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Any, Dict, NewType, Tuple, Union, Type, NamedTuple


class MagicTensorsValue(Enum):
    any = "any"
    same = "same"
    dynamic = "dynamic"


class MagicShapeValue(Enum):
    any = "any"
    dynamic = "dynamic"


class Importable:
    @dataclass
    class Path:
        filepath: str
        callable_name: str


    @dataclass
    class Module:
        module_name: str
        callable_name: str


Source = Union[Importable.Path, Importable.Module]

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
    source: Source
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
    source: Source
    required_kwargs: List[str]
    optional_kwargs: Dict[str, Any]


@dataclass
class Setup:
    reader: ReaderSpec
    sampler: SamplerSpec
    preprocess: List[TransformationSpec]
    postprocess: List[TransformationSpec]
    losses: List[TransformationSpec]
    optimizer: Optimizer


@dataclass
class Training:
    setup: Setup
    source: Source
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
