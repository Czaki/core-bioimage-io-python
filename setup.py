from pathlib import Path
from setuptools import find_namespace_packages, setup

# Get the long description from the README file
long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

# TODO how do we deal with different sub-packages here?
setup(
    name="bioimageio.weight_converter",
    version="0.3b",
    description="Python functionality for the bioimage model zoo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bioimage-io/python-bioimage-io",
    author="Bioimage Team",
    classifiers=[  # Optional
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    packages=find_namespace_packages(exclude=["tests"]),  # Required
    install_requires=[
        "bioimageio.spec @ git+https://github.com/bioimage-io/spec-bioimage-io#egg=bioimageio.spec",
        "imageio>=2.5",
        "numpy"
    ],
    extras_require={"test": ["pytest", "tox"], "dev": ["pre-commit"]},
    project_urls={  # Optional
        "Bug Reports": "https://github.com/bioimage-io/python-bioimage-io/issues",
        "Source": "https://github.com/bioimage-io/python-bioimage-io",
    },
    entry_points={
        "console_scripts": [
            "bioimageio-convert_torch_to_onnx = bioimageio.weight_converter.torch.onnx:main",
            "bioimageio-convert_torch_to_torchscript = bioimageio.weight_converter.torch.torchscript:main"
        ]
    }
)
