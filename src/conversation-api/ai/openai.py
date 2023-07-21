# Import utils
from datetime import datetime
from utils import build_logger, get_config, AZ_CREDENTIAL

# Import misc
from autochain.chain.chain import Chain
from autochain.tools.base import Tool
from models.message import StoredMessageModel, MessageModel
from autochain.memory.buffer_memory import BufferMemory
from autochain.models.chat_openai import ChatOpenAI
from autochain.models.ada_embedding import OpenAIAdaEncoder
from autochain.agent.conversational_agent.conversational_agent import ConversationalAgent
from models.message import MessageRole
from models.user import UserModel
import os
from models.memory import MemoryModel
from typing import Any, List, AsyncGenerator, Optional, Dict
from uuid import UUID, uuid4
from persistence.istore import IStore
import openai
import asyncio
from autochain.agent.message import (
    ChatMessageHistory,
    MessageType,
    SystemMessage,
)
from autochain.memory.base import BaseMemory


###
# Init misc
###

logger = build_logger(__name__)

###
# Init OpenIA
###

openai.api_base = get_config("openai", "api_base", str, required=True)
openai.api_type = "azure_ad"
openai.api_version = "2023-05-15"


class OpenAI:
    _loop: asyncio.AbstractEventLoop
    agent: ConversationalAgent
    embeddings: OpenAIAdaEncoder
    llm: ChatOpenAI
    store: IStore
    tools: List[Tool]

    def __init__(self, store: IStore):
        # Init args
        self.store = store
        self._loop = asyncio.get_running_loop()

        # Init credentials
        os.environ["OPENAI_API_KEY"] = self._generate_token()
        self._loop.create_task(self._refresh_token_background())

        # Init chat
        self.llm = ChatOpenAI(
            model_name=get_config("openai", "gpt_model", str, default="gpt-3.5-turbo", required=True),
        )
        self.tools = [
            Tool(
                description="""This function returns the weather information""",
                func=lambda *args, **kwargs: "Today is a sunny day",
                name="Get weather",
            )
        ]
        self.agent = ConversationalAgent.from_llm_and_tools(llm=self.llm, tools=self.tools)

        # Init embeddings
        self.embeddings = OpenAIAdaEncoder(
            model_name=get_config("openai", "ada_model", str, default="text-embedding-ada-002", required=True),
        )

    async def vector_from_text(self, prompt: str) -> List[float]:
        logger.debug(f"Getting vector for text: {prompt}")
        res = self.embeddings.encode([prompt])
        if len(res.embeddings[0]) > 0:
            return res.embeddings[0]
        return []

    async def completion(self, message: MessageModel, conversation_id: UUID, user_id: UUID) -> SystemMessage:
        memory = Memory(store=self.store, user_id=user_id, conversation_id=conversation_id, secret=message.secret)
        chain = Chain(agent=self.agent, memory=memory, max_execution_time=30)
        return chain.run(message.content)["message"]

    async def chain(self, message: MessageModel, conversation_id: UUID, user_id: UUID) -> AsyncGenerator[str, None]:
        memory = Memory(store=self.store, user_id=user_id, conversation_id=conversation_id, secret=message.secret)
        chain = Chain(agent=self.agent, memory=memory, max_execution_time=30)
        yield chain.run(message.content)["message"]

    async def _refresh_token_background(self):
        """
        Refresh OpenAI token every 15 minutes.

        The OpenAI SDK does not support token refresh, so we need to do it manually. We passe manually the token to the SDK. Azure AD tokens are valid for 30 mins, but we refresh every 15 minutes to be safe.

        See: https://github.com/openai/openai-python/pull/350#issuecomment-1489813285
        """
        while True:
            token = self._generate_token()
            self.embeddings.openai_api_key = token
            self.llm.openai_api_key = token
            # Execute every 20 minutes
            await asyncio.sleep(15 * 60)

    def _generate_token(self):
        logger.info("Refreshing OpenAI token")
        oai_token = AZ_CREDENTIAL.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        return oai_token.token


class Memory(BaseMemory):
    _loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    conversation_id: UUID
    secret: bool
    store: IStore
    user_id: UUID

    class Config:
        arbitrary_types_allowed = True

    def load_memory(self, key: Optional[str] = None, default: Optional[Any] = None, **kwargs) -> Any:
        if key is not None:
            return self.store.memory_get(key, self.user_id) or default
        return default

    def load_conversation(self, **kwargs: Dict[str, Any]) -> ChatMessageHistory:
        history = ChatMessageHistory()
        for message in self.store.message_list(self.conversation_id):
            if message.role == MessageRole.ASSISTANT:
                message_type = MessageType.AIMessage
            elif message.role == MessageRole.USER:
                message_type = MessageType.UserMessage
            elif message.role == MessageRole.FUNCTION:
                message_type = MessageType.FunctionMessage
            elif message.role == MessageRole.SYSTEM:
                message_type = MessageType.SystemMessage
            else:
                raise ValueError(f"Unsupported message role: {message.role}")
            history.save_message(message.content, message_type, **message.extra)

        logger.debug(f"Loaded messages: {history}")
        return history

    def save_memory(self, key: str, value: Any) -> None:
        memory = MemoryModel(
            created_at=datetime.utcnow(),
            id=uuid4(),
            key=key,
            user_id=self.user_id,
            value=value,
        )
        self.store.memory_set(memory)

    def save_conversation(
        self, message: str, message_type: MessageType, **kwargs
    ) -> None:
        if message_type == MessageType.AIMessage:
            role = MessageRole.ASSISTANT
        elif message_type == MessageType.UserMessage:
            role = MessageRole.USER
        elif message_type == MessageType.FunctionMessage:
            role = MessageRole.FUNCTION
        elif message_type == MessageType.SystemMessage:
            role = MessageRole.SYSTEM
        else:
            raise ValueError(f"Unsupported message type: {message_type}")

        # Run async from sync context
        model = StoredMessageModel(
            content=message,
            conversation_id=self.conversation_id,
            created_at=datetime.utcnow(),
            extra=kwargs,
            id=uuid4(),
            role=role,
            secret=self.secret,
            token=uuid4(),
        )
        self.store.message_set(model)

    def clear(self) -> None:
        # TODO: Implement clear method
        logger.debug("Clearing memory")
