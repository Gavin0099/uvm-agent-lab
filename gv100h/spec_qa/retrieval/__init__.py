import importlib
from typing import TYPE_CHECKING, Any

from .governed_retriever import GovernedEvidence, GovernedSpecRetriever

if TYPE_CHECKING:
	from .real_corpus_retriever import (
		GovernedChunkBM25Retriever,
		GovernedChunkRetrievalHit,
		evaluate_retrieval,
	)

_LAZY_REAL_CORPUS_EXPORTS = frozenset(
	{
		"GovernedChunkBM25Retriever",
		"GovernedChunkRetrievalHit",
		"evaluate_retrieval",
	}
)

__all__ = [
	"GovernedEvidence",
	"GovernedSpecRetriever",
]


def __getattr__(name: str) -> Any:
	if name in _LAZY_REAL_CORPUS_EXPORTS:
		module = importlib.import_module(".real_corpus_retriever", __name__)
		return getattr(module, name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
