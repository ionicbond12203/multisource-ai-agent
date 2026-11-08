from api.config import Settings
from api.providers.base import ChatModel, Embedder
from api.providers.fake import ExtractiveChatModel, HashingEmbedder

__all__ = ["ChatModel", "Embedder", "build_providers"]


def build_providers(settings: Settings) -> tuple[Embedder, ChatModel]:
    """Returns the embedder and chat model selected by `LLM_PROVIDER`."""
    match settings.llm_provider:
        case "fake":
            return HashingEmbedder(), ExtractiveChatModel()
