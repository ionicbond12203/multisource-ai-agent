from api.config import Settings
from api.providers.base import ChatModel, Embedder, ProviderError, ProviderRateLimited
from api.providers.fake import ExtractiveChatModel, HashingEmbedder

__all__ = ["ChatModel", "Embedder", "ProviderError", "ProviderRateLimited", "build_providers"]


def build_providers(settings: Settings) -> tuple[Embedder, ChatModel]:
    """Returns the embedder and chat model selected by `LLM_PROVIDER`."""
    match settings.llm_provider:
        case "fake":
            return HashingEmbedder(settings.embedding_dimensions), ExtractiveChatModel()
        case "gemini":
            # Imported here so offline runs don't load the Google SDK.
            from api.providers.gemini import GeminiChatModel, GeminiEmbedder, create_client

            assert settings.gemini_api_key is not None  # checked by Settings
            client = create_client(settings.gemini_api_key.get_secret_value())
            return (
                GeminiEmbedder(client, settings.gemini_embedding_model, settings.embedding_dimensions),
                GeminiChatModel(client, settings.gemini_chat_model, settings.gemini_thinking_level),
            )
