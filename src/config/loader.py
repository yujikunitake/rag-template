import os

import yaml

from src.config.schema import PipelineConfig

SECTIONS = ("chunker", "embedder", "retriever", "reranker", "generator")


def load_config(path: str) -> PipelineConfig:
    with open(path) as f:
        data = yaml.safe_load(f)

    for section in SECTIONS:
        prefix = f"{section.upper()}__"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                field = key[len(prefix) :].lower()
                data.setdefault(section, {})[field] = value

    return PipelineConfig(**data)
