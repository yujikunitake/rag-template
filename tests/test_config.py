import pytest
from pydantic import ValidationError

from src.config.loader import load_config
from src.config.schema import ChunkerConfig, PipelineConfig

VALID_YAML = """\
chunker:
  strategy: fixed_size
  chunk_size: 512
  overlap: 64
embedder:
  model: nomic-embed-text-v1.5
  device: mps
retriever:
  strategy: vector
  top_k: 5
  mmr_lambda: 0.5
reranker:
  enabled: false
  model: unicamp-dl/InRanker-small
generator:
  provider: openrouter
  default_model: deepseek/deepseek-chat-v3
  fallback_model: google/gemini-flash-1.5
"""


def test_config_loads_valid_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)

    config = load_config(str(config_file))

    assert isinstance(config, PipelineConfig)
    assert config.chunker.strategy == "fixed_size"
    assert config.chunker.chunk_size == 512
    assert config.embedder.device == "mps"
    assert config.retriever.top_k == 5
    assert config.reranker.enabled is False
    assert config.generator.default_model == "deepseek/deepseek-chat-v3"


def test_config_rejects_invalid_type():
    with pytest.raises(ValidationError):
        ChunkerConfig(strategy="fixed_size", chunk_size="cem", overlap=64)


def test_config_rejects_missing_field():
    with pytest.raises(ValidationError):
        ChunkerConfig(chunk_size=512, overlap=64)


def test_env_var_overrides_yaml(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)
    monkeypatch.setenv("EMBEDDER__DEVICE", "cpu")

    config = load_config(str(config_file))

    assert config.embedder.device == "cpu"
