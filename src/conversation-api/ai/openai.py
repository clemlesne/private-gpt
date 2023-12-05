from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from datetime import datetime
from helpers.config import CONFIG
from helpers.func import try_or_none, sanitize
from helpers.logging import build_logger
from langchain_core.globals import set_verbose as set_langchain_verbose
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.callbacks import get_openai_callback
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings import AzureOpenAIEmbeddings
from langchain.memory import ConversationSummaryMemory, ReadOnlySharedMemory
from langchain.prompts import PromptTemplate
from langchain.schema import BaseChatMessageHistory, AgentAction
from langchain.schema.messages import AIMessage, BaseMessage, HumanMessage
from langchain.tools import YouTubeSearchTool, PubmedQueryRun
from langchain.tools.azure_cognitive_services import AzureCogsFormRecognizerTool
from langchain.tools.base import Tool, BaseTool, ToolException
from langchain.tools.google_places import GooglePlacesTool
from langchain.tools.requests.tool import RequestsGetTool
from langchain.utilities.requests import TextRequestsWrapper
from langchain.vectorstores.azuresearch import AzureSearch
from models.conversation import StoredConversationModel
from models.message import MessageRole
from models.message import StoredMessageModel, MessageModel, StreamMessageModel
from models.user import UserModel
from openai import BadRequestError, APIError
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
import asyncio
import textwrap
import os


_logger = build_logger(__name__)
set_langchain_verbose(True)  # TODO: Make this dynamic based on debug level

AZ_CREDENTIAL = DefaultAzureCredential()
AZ_TOKEN_PROVIDER = get_bearer_token_provider(
    AZ_CREDENTIAL, "https://cognitiveservices.azure.com/.default"
)

CUSTOM_PREFIX = f"""
Assistant is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics.

Today, we are the {datetime.utcnow()}.

Only in its final answer:
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

os.environ["GPLACES_API_KEY"] = CONFIG.tools.google_places.api_key.get_secret_value()


class OpenAI:
    _loop: asyncio.AbstractEventLoop
    _chat: AzureChatOpenAI
    _gpt_max_input_tokens: int
    search: ISearch
    _store: IStore
    _tools: List[BaseTool] = []

    def __init__(self, store: IStore):
        self._loop = asyncio.get_running_loop()
        self._store = store

        # Misc
        self._gpt_max_input_tokens = CONFIG.ai.openai.gpt_max_input_tokens
        # TODO: Use azure_ad_token_provider instead of api_key, when it'll be debuged (https://github.com/langchain-ai/langchain/issues/14069)
        openai_kwargs = {
            "api_version": "2023-05-15",  # Latest stable as of Nov 30 2023
            "azure_ad_token": AZ_TOKEN_PROVIDER(),
            "azure_endpoint": str(CONFIG.ai.openai.endpoint),
            "max_retries": 10,  # Catch 429 Too Many Requests
            "request_timeout": 30,
        }

        # Init chat
        self._chat = AzureChatOpenAI(
            azure_deployment=CONFIG.ai.openai.gpt_deployment,
            model=CONFIG.ai.openai.gpt_model,
            streaming=True,
            temperature=0,
            **openai_kwargs,
        )

        # Init embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=CONFIG.ai.openai.ada_deployment,
            embedding_ctx_length=CONFIG.ai.openai.ada_max_input_tokens,
            model=CONFIG.ai.openai.ada_model,
            **openai_kwargs,
        )

        # Setup token refresh
        self._loop.create_task(self._refresh_ad_token())

        # Setup tools
        self._init_default_tools()
        self._init_custom_tools()
        self._init_cognitive_search_tools()

    def _init_default_tools(self):
        self._tools += load_tools(
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
            bing_search_url=str(CONFIG.tools.bing.search_url),  # bing-search
            bing_subscription_key=CONFIG.tools.bing.subscription_key.get_secret_value(),  # bing-search
            listen_api_key=CONFIG.tools.listen_notes.api_key.get_secret_value(),  # podcast-api
            llm=self._chat,  # llm-math
            news_api_key=CONFIG.tools.news.api_key.get_secret_value(),  # news-api
            openweathermap_api_key=CONFIG.tools.open_weather_map.api_key.get_secret_value(),  # openweathermap-api
            tmdb_bearer_token=CONFIG.tools.tmdb.bearer_token.get_secret_value(),  # tmdb-api
            top_k_results=10,  # wikipedia, arxiv
        )

    def _init_custom_tools(self):
        req_tool = RequestsGetTool(requests_wrapper=TextRequestsWrapper())
        self._tools += [
            PubmedQueryRun(),
            YouTubeSearchTool(),
            AzureCogsFormRecognizerTool(
                azure_cogs_endpoint=str(CONFIG.tools.azure_form_recognizer.api_base),
                azure_cogs_key=CONFIG.tools.azure_form_recognizer.api_token.get_secret_value(),
            ),  # type: ignore
            GooglePlacesTool(
                description="Useful for when you need to validate addresses or get details about places (incl. address, phone, website). Input should be a search query.",
            ),  # Requires GPLACES_API_KEY env var
            Tool(
                description=f"{req_tool.description} Use this to download the content of a HTTP link. Link requires to be either HTML, or text (example: XML, JSON). Output will be reduced to its characters, no text formatting will be applied.",
                func=lambda *args, **kwargs: (
                    sanitize(try_or_none(req_tool.run, *args, **kwargs)) or str()
                )[
                    : int(self._gpt_max_input_tokens)
                ],  # Tokens count is not the same as characters, but it's a sufficient approximation
                name=req_tool.name,
            ),
            Tool(
                description="Useful for when you need to generate ideas, write articles, search new point of views. If the result of this function is similar to the previous one, do not use it. Input should be a string, representing the idea. The output will be a text describing the idea.",
                func=lambda q: self._chat.predict(q),
                name="imagination",
            ),
            Tool(
                description="Useful for when you need to summarize a text. Input should be a string, representing the text to summarize. The output will be a text describing the text.",
                func=lambda q: load_summarize_chain(self._chat).run(q),
                name="summarize",
            ),
        ]

    def _init_cognitive_search_tools(self):
        azure_cognitive_searches = CONFIG.tools.azure_cognitive_search
        for instance in azure_cognitive_searches:
            _logger.debug(f"Loading Azure Cognitive Search custom tool: {instance}")
            tool = Tool(
                description=textwrap.dedent(
                    f"""
                Usage: {instance.usage}.

                Constraints:
                - Input should be a string, representing an keywords list for the search.
                - Keywords requires to be extended with related ideas and synonyms.
                - The output will be a list of messages. Data can be truncated is the message is too long.

                Here are some examples:

                User query: General taxes report for 2020 in the Massachusetts state
                Query: 2020 taxes report in Massachusetts USA

                User query: Issue on this metal piece in the form of a triangle with a hole in the middle
                Query: Triangle of metal with a hole

                User query: What do I do after I have been in a car accident?
                Query: Car accident instructions

                Do not reference any of the examples above.
                """
                ),
                func=lambda q, api_key=instance.api_key.get_secret_value(), index_name=instance.displayed_name, language=instance.language, semantic_configuration=instance.semantic_configuration, service_name=instance.service_name, top_k=instance.top_k: str(
                    [
                        sanitize(doc.page_content)
                        for doc in AzureSearch(
                            azure_search_endpoint=f"https://{service_name}.search.windows.net",
                            azure_search_key=api_key,
                            embedding_function=self.embeddings.embed_query,
                            index_name=index_name,
                            semantic_configuration_name=semantic_configuration,
                            semantic_query_language=language,
                        ).similarity_search(
                            k=top_k,
                            query=q,
                        )
                    ]
                )[
                    : int(self._gpt_max_input_tokens)
                ],  # Tokens count is not the same as characters, but it's a sufficient approximation
                name=f"{instance.displayed_name} (Azure Cognitive Search)",
            )
            self._tools.append(tool)

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
            message_callback(self._chat.predict(prompt))
            usage_callback(cb.total_tokens, self._chat.model_name)

    @retry(
        retry=(
            retry_if_result(
                lambda res: res == "Agent stopped due to iteration limit or time limit."
            )
            | retry_if_exception_type((BadRequestError, APIError))
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
        # Setup memory
        message_history = CustomHistory(
            conversation_id=conversation.id,
            secret=message.secret,
            store=self._store,
            user_id=current_user.id,
        )
        # Also can use ConversationSummaryBufferMemory, which can be used to summarize the conversation if it is too long
        memory = ConversationSummaryMemory(
            chat_memory=message_history,
            llm=self._chat,
            memory_key="chat_history",
            return_messages=True,
        )
        # Protect memory from being modified by the tools
        readonly_memory = ReadOnlySharedMemory(memory=memory)

        # Setup personalized tools
        tools = [
            *self._tools,
            Tool(
                func=lambda q: str(
                    [
                        f'{answer.data.role}, {sanitize(answer.data.content) or "No content"}'
                        for answer in self.search.message_search(
                            q, current_user.id, 5
                        ).answers
                    ]
                )[
                    : int(self._gpt_max_input_tokens)
                ],  # Tokens count is not the same as characters, but it's a sufficient approximation
                description="Useful for when you need past user messages, from other conversations. Input should be a string, representing the search query written in semantic language. The output will be a list of 5 messages as JSON objects.",
                name="messages_search",
            ),
        ]

        # Setup personalized prompt
        prefix = (
            CUSTOM_PREFIX
            + "\n\n"
            + textwrap.dedent(
                f"""
            Only in its final answer, Assistant SHOULD:
            {conversation.prompt.content if conversation.prompt else "None"}

            User profile:
            - Email: {current_user.email}
            - ID: {current_user.preferred_username}
            - Name: {current_user.name}
            """
            )
        )

        # Run
        agent = initialize_agent(
            agent_kwargs={
                "verbose": True,
                "input_variables": [
                    "agent_scratchpad",
                    "chat_history",
                    "input",
                    "language",
                ],
                "system_message": prefix,
            },
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,  # TODO: Test using OPENAI_MULTI_FUNCTIONS, but fails to read memory
            # early_stopping_method="generate",  # Fix in progress, see: https://github.com/langchain-ai/langchain/issues/8249#issuecomment-1651074268
            handle_parsing_errors=True,  # Catch tool parsing errors
            llm=self._chat,
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

            try:
                res = agent.run(input=message.content, language=language)
            except ToolException as e:
                _logger.error(f"Tool error: {e}")
                res = "Data error, please try again later."

            _logger.debug(f"Agent response: {res}")
            message_callback(StreamMessageModel(content=res))
            usage_callback(cb.total_tokens, self._chat.model_name)

    async def _refresh_ad_token(self):
        """
        Refresh OpenAI token every 20 minutes.

        The OpenAI SDK does not support token refresh, so we need to do it manually. We passe manually the token to the SDK. Azure AD tokens are valid for 30 mins, but we refresh earlier to be safe.

        See: https://github.com/openai/openai-python/pull/350#issuecomment-1489813285
        """
        while True:
            ad_token = AZ_TOKEN_PROVIDER()
            self._chat.azure_ad_token = ad_token
            self.embeddings.azure_ad_token = ad_token
            await asyncio.sleep(60 * 20)


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
                obj = AIMessage(
                    content=message.content, additional_kwargs=message.extra
                )
            elif message.role == MessageRole.USER:
                obj = HumanMessage(
                    content=message.content, additional_kwargs=message.extra
                )
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
