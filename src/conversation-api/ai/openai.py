# Import utils
from utils import build_logger, get_config, AZ_CREDENTIAL, try_or_none, sanitize

# Import misc
from datetime import datetime
from langchain import PromptTemplate
from langchain.agents import AgentType, initialize_agent, load_tools, Tool
from langchain.agents.structured_chat.prompt import PREFIX as DEFAULT_PREFIX
from langchain.callbacks import get_openai_callback
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.memory import ConversationBufferMemory, ReadOnlySharedMemory
from langchain.prompts import MessagesPlaceholder
from langchain.retrievers import AzureCognitiveSearchRetriever
from langchain.schema import BaseChatMessageHistory, ChatGeneration, AgentAction
from langchain.schema.cache import BaseCache
from langchain.schema.messages import AIMessage, BaseMessage, HumanMessage
from langchain.tools import YouTubeSearchTool, PubmedQueryRun
from langchain.tools.azure_cognitive_services import AzureCogsFormRecognizerTool
from langchain.tools.base import Tool
from langchain.tools.google_places import GooglePlacesTool
from langchain.tools.office365.create_draft_message import O365CreateDraftMessage
from langchain.tools.office365.events_search import O365SearchEvents
from langchain.tools.office365.messages_search import O365SearchEmails
from langchain.tools.requests.tool import RequestsGetTool
from langchain.utilities.requests import TextRequestsWrapper
from models.conversation import StoredConversationModel
from models.message import MessageRole
from models.message import StoredMessageModel, MessageModel, StreamMessageModel
from models.user import UserModel
from O365 import Account
from openai.error import InvalidRequestError, APIError
from persistence.icache import ICache
from persistence.isearch import ISearch
from persistence.istore import IStore
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    retry_if_result,
)
from typing import Any, Callable, List, Optional, Sequence
from uuid import UUID
import urllib.parse
import asyncio
import textwrap
import os


###
# Init misc
###

_logger = build_logger(__name__)

CUSTOM_PREFIX = f"""
Assistant is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics.

Today, we are the {datetime.utcnow()}.

Only in its final answer, Assistant MUST:
- Answer in the language {{language}}, or in the language the user explicitly asked for
- Be as accurate as possible
- Be polite, respectful, and positive
- Cite a maximum of sources (URLs, law) used to build the response, as a list and with the following format: [Author, Year, Title] with a HTTP link (example: [Microsoft, 2021, Microsoft Certified: Azure Solutions Architect Expert - Certifications](https://learn.microsoft.com/en-gb/certifications/azure-solutions-architect))
- Never cite the tools you have used
- Specify the language name when you write source code (example: ```python\\n...\\n```, or ```bash\\n...\\n```)
- Try to find at least one source to support your answer, two is better
- Use Markdown syntax for formatting for bold, italic, code blocks, and links (example: **bold**, *italic*, `code`, [link](https://bing.com))
- Use the name of the user when you address them (example: "Hello John, how are you?")
- Write emojis as gemoji shortcodes (example: :smile:)
"""

###
# Init auth for tools
###

os.environ["GPLACES_API_KEY"] = get_config(["tools", "google_places"], "api_key", str, required=True)


class OpenAI:
    _loop: asyncio.AbstractEventLoop
    chat: AzureChatOpenAI
    gpt_max_tokens: int
    search: ISearch
    store: IStore
    tools: Sequence[Tool]

    def __init__(self, store: IStore):
        self._loop = asyncio.get_running_loop()
        self.store = store

        # Init credentials
        oai_token = self._generate_token()
        self._loop.create_task(self._refresh_token_background())

        # Misc
        self.gpt_max_tokens = get_config(
            ["ai", "openai"], "gpt_max_tokens", int, required=True
        )
        openai_args = {
            "openai_api_base": get_config(
                ["ai", "openai"], "api_base", str, required=True
            ),
            "openai_api_key": oai_token,
            "openai_api_type": "azure_ad",
            "openai_api_version": "2023-05-15",
            "request_timeout": 30,
            "temperature": 0,
            "verbose": True,
        }

        # Init chat
        self.chat = AzureChatOpenAI(
            deployment_name=get_config(
                ["ai", "openai"], "gpt_deploy_id", str, required=True
            ),
            streaming=True,
            **openai_args,
        )
        self.tools = load_tools(
            [
                "arxiv",  # Search scholarly articles with Arxiv
                "bing-search",  # Search the web with Bing
                "llm-math",  # Math operations with a LLM
                "news-api",  # Search news with NewsAPI
                "openweathermap-api",  # Get weather with OpenWeatherMap
                "podcast-api",  # Search podcasts with ListenNotes
                "tmdb-api",  # Search movies with TMDB
                "wikipedia",  # Search general articles with Wikipedia
            ],
            top_k_results=5,  # wikipedia, arxiv
            openweathermap_api_key=get_config(
                ["tools", "open_weather_map"], "api_key", str, required=True
            ),  # openweathermap-api
            news_api_key=get_config(
                ["tools", "news"], "api_key", str, required=True
            ),  # news-api
            bing_search_url=get_config(
                ["tools", "bing"], "search_url", str, required=True
            ),  # bing-search
            bing_subscription_key=get_config(
                ["tools", "bing"], "subscription_key", str, required=True
            ),  # bing-search
            listen_api_key=get_config(
                ["tools", "listen_notes"], "api_key", str, required=True
            ),  # podcast-api
            llm=self.chat,  # llm-math
            tmdb_bearer_token=get_config(
                ["tools", "tmdb"], "bearer_token", str, required=True
            ),  # tmdb-api
        )
        req_tool = RequestsGetTool(requests_wrapper=TextRequestsWrapper())
        self.tools += [
            PubmedQueryRun(),
            YouTubeSearchTool(),
            AzureCogsFormRecognizerTool(
                azure_cogs_endpoint=get_config(
                    ["tools", "azure_form_recognizer"], "api_base", str, required=True
                ),
                azure_cogs_key=get_config(
                    ["tools", "azure_form_recognizer"], "api_token", str, required=True
                ),
            ),
            GooglePlacesTool(
                description="Useful for when you need to validate addresses or get details about places (incl. address, phone, website). Input should be a search query.",
            ),  # Requires GPLACES_API_KEY env var
            Tool(
                description=f"{req_tool.description} Use this to download the content of a HTTP link. Link requires to be either HTML, or text (example: XML, JSON). Output will be reduced to its characters, no text formatting will be applied.",
                func=lambda *args, **kwargs: (
                    sanitize(try_or_none(req_tool.run, *args, **kwargs)) or str()
                )[: int(self.gpt_max_tokens)],
                name=req_tool.name,
            ),
            Tool(
                description="Useful for when you need to generate ideas, write articles, search new point of views. If the result of this function is similar to the previous one, do not use it. Input should be a string, representing the idea. The output will be a text describing the idea.",
                func=lambda q: self.chat.predict(q),
                name="imagination",
            ),
            Tool(
                description="Useful for when you need to summarize a text. Input should be a string, representing the text to summarize. The output will be a text describing the text.",
                func=lambda q: load_summarize_chain(self.chat).run(q),
                name="summarize",
            ),
        ]
        # Azure Cognitive Search
        for instance in get_config(
            "tools", "azure_cognitive_search", list, required=True
        ):
            _logger.debug(f"Loading Azure Cognitive Search custom tool: {instance}")
            # Parameters
            api_key = instance.get("api_key")
            content_key = instance.get("content_key")
            displayed_name = instance.get("displayed_name")
            index_name = instance.get("index_name")
            language = instance.get("language")
            semantic_configuration = instance.get("semantic_configuration")
            service_name = instance.get("service_name")
            top_k = instance.get("top_k")
            usage = instance.get("usage")
            # Create tool
            tool = Tool(
                description=f"{usage} Input should be a string, representing an keywords list for the search. Keywords requires to be extended with related ideas and synonyms. The output will be a list of messages. Data can be truncated is the message is too long.",
                func=lambda q, api_key=api_key, content_key=content_key, index_name=index_name, language=language, semantic_configuration=semantic_configuration, service_name=service_name, top_k=top_k: str(
                    [
                        sanitize(doc.page_content)
                        for doc in AzureCognitiveSearchSemanticRetriever(
                            api_key=api_key,
                            content_key=content_key,
                            index_name=index_name,
                            query_language=language,
                            semantic_configuration=semantic_configuration,
                            service_name=service_name,
                            top_k=top_k,
                        ).get_relevant_documents(q)
                    ]
                )[
                    : int(self.gpt_max_tokens)
                ],
                name=f"{displayed_name} (Azure Cognitive Search)",
            )
            self.tools.append(tool)

        # Init embeddings
        self.embeddings = OpenAIEmbeddings(
            deployment=get_config(
                ["ai", "openai"], "ada_deploy_id", str, required=True
            ),
            model_kwargs={
                "model_name": get_config(
                    ["ai", "openai"],
                    "ada_model",
                    str,
                    default="text-embedding-ada-002",
                    required=True,
                ),
            },
            **openai_args,
        )

    def vector_from_text(self, prompt: str) -> List[float]:
        _logger.debug(f"Getting vector for text: {prompt}")
        return self.embeddings.embed_query(prompt)

    async def completion(
        self,
        message: MessageModel,
        template: str,
        language: str,
        message_callback: Callable[[str], None],
        usage_callback: Callable[[int, str], None],
    ) -> None:
        builder = PromptTemplate(
            template=template, input_variables=["language", "query"]
        )
        prompt = builder.format(query=message.content, language=language)
        _logger.debug(f"Asking completion with prompt: {prompt}")

        with get_openai_callback() as cb:
            message_callback(self.chat.predict(prompt))
            usage_callback(cb.total_tokens, self.chat.model_name)

    @retry(
        retry=(
            retry_if_result(
                lambda res: res == "Agent stopped due to iteration limit or time limit."
            )
            | retry_if_exception_type((InvalidRequestError, APIError))
        ),
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    async def chain(
        self,
        message: MessageModel,
        conversation: StoredConversationModel,
        current_user: UserModel,
        language: str,
        message_callback: Callable[[StreamMessageModel], None],
        usage_callback: Callable[[int, str], None],
    ) -> None:
        # Setup memory
        memory_var = "chat_history"
        message_history = CustomHistory(
            conversation_id=conversation.id,
            secret=message.secret,
            store=self.store,
            user_id=current_user.id,
        )
        # Also can use ConversationSummaryBufferMemory, which can be used to summarize the conversation if it is too long
        memory = ConversationBufferMemory(
            chat_memory=message_history,
            memory_key=memory_var,
            return_messages=True,
        )
        # Protect memory from being modified by the tools
        readonly_memory = ReadOnlySharedMemory(memory=memory)

        # Setup Office 365 account
        o365_account = Account(
            credentials=(current_user.external_id, current_user.login_hint),
            scopes=[
                "Calendars.ReadWrite",
                "Mail.ReadWrite",
            ]
        )

        # Fix type checking in Pydantic, as Account O365 import is conditional in O365BaseTool LangChain class
        O365CreateDraftMessage.update_forward_refs(Account=Account)
        O365SearchEmails.update_forward_refs(Account=Account)
        O365SearchEvents.update_forward_refs(Account=Account)

        # Setup personalized tools
        tools = [
            *self.tools,
            O365CreateDraftMessage(account=o365_account),
            O365SearchEmails(account=o365_account),
            O365SearchEvents(account=o365_account),
            Tool(
                func=lambda q: str(
                    [
                        f'{answer.data.role}, {sanitize(answer.data.content) or "No content"}'
                        for answer in self.search.message_search(
                            q, current_user.id, 5
                        ).answers
                    ]
                )[: int(self.gpt_max_tokens)],
                description="Useful for when you need past user messages, from other conversations. Input should be a string, representing the search query written in semantic language. The output will be a list of 5 messages as JSON objects.",
                name="messages_search",
            ),
        ]

        # Setup personalized prompt
        memory_prompt = MessagesPlaceholder(variable_name=memory_var)
        prefix = textwrap.dedent(
            f"""
            {CUSTOM_PREFIX}

            Only in its final answer, Assistant SHOULD:
            {conversation.prompt.content if conversation.prompt else "None"}

            User profile:
            - Email: {current_user.email}
            - ID: {current_user.preferred_username}
            - Name: {current_user.name}

            {DEFAULT_PREFIX}
        """
        )

        # Run
        agent = initialize_agent(
            agent_kwargs={
                "memory_prompts": [memory_prompt],
                "prefix": prefix,
                "verbose": True,
                "input_variables": [
                    "agent_scratchpad",
                    "input",
                    "language",
                    memory_var,
                ],
            },
            # agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,  # Support multi-input tools, but bugy (https://github.com/langchain-ai/langchain/issues/5870)
            # early_stopping_method="generate",  # Fix in progress, see: https://github.com/langchain-ai/langchain/issues/8249#issuecomment-1651074268
            handle_parsing_errors=True,  # Catch tool parsing errors
            llm=self.chat,
            max_execution_time=60,  # Timeout
            max_iterations=15,
            memory=readonly_memory,
            tools=tools,
            verbose=True,
        )

        def on_agent_action(action: AgentAction, **kwargs):
            if action.tool == "_Exception":
                _logger.error(f"Agent error: {action}")
                return

            message_callback(StreamMessageModel(action=action.tool))

        with get_openai_callback() as cb:
            cb.on_agent_action = on_agent_action
            res = agent.run(input=message.content, language=language)
            _logger.debug(f"Agent response: {res}")
            message_callback(StreamMessageModel(content=res))
            usage_callback(cb.total_tokens, self.chat.model_name)

    async def _refresh_token_background(self):
        """
        Refresh OpenAI token every 15 minutes.

        The OpenAI SDK does not support token refresh, so we need to do it manually. We passe manually the token to the SDK. Azure AD tokens are valid for 30 mins, but we refresh every 15 minutes to be safe.

        See: https://github.com/openai/openai-python/pull/350#issuecomment-1489813285
        """
        while True:
            token = self._generate_token()
            self.chat.openai_api_key = token
            self.embeddings.openai_api_key = token
            # Execute every 20 minutes
            await asyncio.sleep(15 * 60)

    def _generate_token(self):
        _logger.info("Refreshing OpenAI token")
        oai_token = AZ_CREDENTIAL.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        return oai_token.token


class CustomCache(BaseCache):
    PREFIX = "prompt"
    cache: ICache

    def __init__(self, cache: ICache):
        self.cache = cache

    def lookup(self, prompt: str, llm_string: str) -> Optional[List[ChatGeneration]]:
        raws = self.cache.hget(self._key(prompt, llm_string))
        if not raws:
            return None
        generations = []
        for json, role_str in raws.items():
            _logger.debug(f"Loading cached message: {json}")
            try:
                message = None
                role_enum = MessageRole(role_str)
                if role_enum == MessageRole.ASSISTANT:
                    message = AIMessage.parse_raw(json)
                elif role_enum == MessageRole.USER:
                    message = HumanMessage.parse_raw(json)
                else:
                    _logger.warn(f"Unsupported message role: {role_enum}")
                if message:
                    generations.append(ChatGeneration(message=message))
            except Exception:
                _logger.warn("Error parsing cached messages", exc_info=True)
        _logger.debug(f"Loaded generations from cache: {generations}")
        return generations if generations else None

    def update(
        self, prompt: str, llm_string: str, return_val: List[ChatGeneration]
    ) -> None:
        messages = {}
        for generation in return_val:
            message = generation.message
            if not message:
                _logger.debug(f"Generation does not contain message: {generation}")
                continue
            role_enum = None
            if isinstance(message, AIMessage):
                role_enum = MessageRole.ASSISTANT
            elif isinstance(message, HumanMessage):
                role_enum = MessageRole.USER
            else:
                _logger.warn(f"Unsupported message type: {type(message)}")
            if role_enum:
                messages[message.json()] = role_enum.value
        if messages:
            _logger.debug(f"Updating cache with messages: {messages}")
            self.cache.hset(
                self._key(prompt, llm_string),
                messages,
            )

    def clear(self, **kwargs: Any) -> None:
        # Clear not implemented, we don't want to clear storage layer
        pass

    def _key(self, prompt: str, llm_string: str) -> str:
        return f"{self.PREFIX}:{prompt}:{llm_string}"


class CustomHistory(BaseChatMessageHistory):
    conversation_id: UUID
    secret: bool
    store: IStore
    user_id: UUID

    def __init__(
        self, conversation_id: UUID, secret: bool, store: IStore, user_id: UUID
    ):
        self.conversation_id = conversation_id
        self.secret = secret
        self.store = store
        self.user_id = user_id

    @property
    def messages(self) -> List[BaseMessage]:
        res = []
        for message in self.store.message_list(self.conversation_id) or []:
            if message.role == MessageRole.ASSISTANT:
                obj = AIMessage(content=message.content, **message.extra)
            elif message.role == MessageRole.USER:
                obj = HumanMessage(content=message.content, **message.extra)
            else:
                raise ValueError(f"Unsupported message role: {message.role}")
            res.append(obj)
        _logger.debug(f"Loaded messages: {res}")
        return res

    def add_message(self, message: BaseMessage) -> None:
        if isinstance(message, AIMessage):
            role = MessageRole.ASSISTANT
        elif isinstance(message, HumanMessage):
            role = MessageRole.USER
        else:
            raise ValueError(f"Unsupported message type: {type(message)}")

        self.store.message_set(
            StoredMessageModel(
                content=message.content,
                conversation_id=self.conversation_id,
                extra=message.additional_kwargs,
                role=role,
                secret=self.secret,
            )
        )

    def add_user_message(self, message: str) -> None:
        self.store.message_set(
            StoredMessageModel(
                content=message,
                conversation_id=self.conversation_id,
                role=MessageRole.USER,
                secret=self.secret,
            )
        )

    def add_ai_message(self, message: str) -> None:
        self.store.message_set(
            StoredMessageModel(
                content=message,
                conversation_id=self.conversation_id,
                role=MessageRole.ASSISTANT,
                secret=self.secret,
            )
        )

    def clear(self) -> None:
        # Clear not implemented, we don't want to clear storage layer
        pass


class AzureCognitiveSearchSemanticRetriever(AzureCognitiveSearchRetriever):
    """
    Azure Cognitive Search retriever with semantic search.

    Native LangChain implementation is not used because it does not support semantic search.

    See:
    - API doc: https://learn.microsoft.com/en-us/rest/api/searchservice/preview-api/search-documents
    - Native implementation: https://github.com/langchain-ai/langchain/blob/v0.0.281/libs/langchain/langchain/retrievers/azure_cognitive_search.py
    """

    api_version: str = "2023-07-01-Preview"
    query_language: str = ""
    semantic_configuration: str = ""

    def _build_search_url(self, query: str) -> str:
        params = urllib.parse.urlencode(
            {
                "api-version": self.api_version,
                "search": query,
                "top": self.top_k,
                # Semantic search
                "queryType": "semantic",
                "semanticConfiguration": self.semantic_configuration,
                # Language ranker
                "queryLanguage": self.query_language,
                "speller": "lexicon",  # Required param for both semantic and language ranker
            }
            | {
                "top": self.top_k,
            }
            if self.top_k
            else {}
        )
        url = (
            f"https://{self.service_name}.search.windows.net/indexes/{self.index_name}/docs?"
            + params
        )
        _logger.debug(f"Built search URL: {url}")
        return url
