from pydantic import BaseModel


class ChunkerConfig(BaseModel):
    strategy: str
    chunk_size: int
    overlap: int


class EmbedderConfig(BaseModel):
    model: str
    device: str


class RetrieverConfig(BaseModel):
    strategy: str
    top_k: int
    mmr_lambda: float


class RerankerConfig(BaseModel):
    enabled: bool
    model: str


class GeneratorConfig(BaseModel):
    provider: str
    default_model: str
    fallback_model: str


class PipelineConfig(BaseModel):
    chunker: ChunkerConfig
    embedder: EmbedderConfig
    retriever: RetrieverConfig
    reranker: RerankerConfig
    generator: GeneratorConfig
