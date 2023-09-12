# Import utils
from utils import (
    build_logger,
    get_config,
    hash_token,
    VerifyToken,
    VERSION,
)

# Import misc
from ai.contentsafety import ContentSafety
from ai.openai import OpenAI, CustomCache
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.conversation import (
    GetConversationModel,
    ListConversationsModel,
    StoredConversationModel,
)
from models.message import (
    MessageModel,
    MessageRole,
    StoredMessageModel,
    StreamMessageModel,
)
from models.prompt import StoredPromptModel, ListPromptsModel
from models.readiness import ReadinessModel, ReadinessCheckModel, ReadinessStatus
from models.search import SearchModel
from models.usage import UsageModel
from models.user import UserModel
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from persistence.icache import CacheImplementation
from persistence.isearch import SearchImplementation
from persistence.istore import StoreImplementation
from persistence.istream import StreamImplementation
from sse_starlette.sse import EventSourceResponse
from typing import Annotated, Dict, List, Optional
from uuid import UUID
from uuid import uuid4
import asyncio
import csv
import langchain


###
# Init misc
###

_logger = build_logger(__name__)
_loop = asyncio.get_running_loop()

###
# Init persistence
###

# Cache
cache_impl = get_config("persistence", "cache", CacheImplementation, required=True)
try:
    if cache_impl == CacheImplementation.REDIS:
        from persistence.redis import RedisCache

        cache = RedisCache()
    else:
        raise ValueError(f"Unknown cache implementation: {cache_impl}")
    _logger.info(f'Using "{type(cache).__name__}" as cache backend')
except Exception as e:
    _logger.error("Failed to initialize cache engine", exc_info=True)
    exit(1)
# Configure LangChain accordingly
langchain.llm_cache = CustomCache(cache=cache)

# Store
store_impl = get_config("persistence", "store", StoreImplementation, required=True)
try:
    if store_impl == StoreImplementation.COSMOS:
        from persistence.cosmos import CosmosStore

        store = CosmosStore(cache)
    elif store_impl == StoreImplementation.CACHE:
        from persistence.cache import CacheStore

        store = CacheStore(cache)
    else:
        raise ValueError(f"Unknown store implementation: {store_impl}")
    _logger.info(f'Using "{type(store).__name__}" as store backend')
except Exception as e:
    _logger.error("Failed to initialize store engine", exc_info=True)
    exit(1)

###
# Init Generative AI
###

openai = OpenAI(store)
content_safety = ContentSafety()

###
# Init persistence
###

# Search
search_impl = get_config("persistence", "search", SearchImplementation, required=True)
try:
    if search_impl == SearchImplementation.QDRANT:
        from persistence.qdrant import QdrantSearch

        index = QdrantSearch(store, cache, openai)
    else:
        raise ValueError(f"Unknown search implementation: {search_impl}")
    _logger.info(f'Using "{type(index).__name__}" as search backend')
except Exception as e:
    _logger.error("Failed to initialize search engine", exc_info=True)
    exit(1)
# Configure OpenAI accordingly
openai.search = index

# Stream
stream_impl = get_config("persistence", "stream", StreamImplementation, required=True)
try:
    if stream_impl == StreamImplementation.REDIS:
        from persistence.redis import RedisStream

        stream = RedisStream()
    else:
        raise ValueError(f"Unknown stream implementation: {stream_impl}")
    _logger.info(f'Using "{type(stream).__name__}" as stream backend')
except Exception as e:
    _logger.error("Failed to initialize stream engine", exc_info=True)
    exit(1)

###
# Init FastAPI
###

ROOT_PATH = get_config("api", "root_path", str, default="")
_logger.info(f'Using root path "{ROOT_PATH}"')

api = FastAPI(
    contact={
        "url": "https://github.com/clemlesne/private-gpt",
    },
    description="Private GPT is a local version of Chat GPT, using Azure OpenAI.",
    license_info={
        "name": "Apache-2.0",
        "url": "https://github.com/clemlesne/private-gpt/blob/master/LICENSE",
    },
    root_path=ROOT_PATH,
    title="conversation-api",
    version=VERSION,
)
auth_scheme = HTTPBearer()

# Setup CORS
api.add_middleware(
    CORSMiddleware,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"],
)

###
# Init Generative AI
###


def get_ai_prompt() -> Dict[UUID, StoredPromptModel]:
    prompts = {}
    with open("data/prompts.csv", newline="") as f:
        rows = csv.reader(f)
        next(rows, None)  # Skip header
        for row in rows:
            name = row[0]
            content = row[1]
            group = row[2]
            prompt = StoredPromptModel(
                id=hash_token(name), name=name, content=content, group=group
            )
            prompts[prompt.id] = prompt
    _logger.info(f"Loaded {len(prompts)} prompts")
    # Sort by name asc
    return dict(sorted(prompts.items(), key=lambda i: i[1].name))


AI_PROMPTS = get_ai_prompt()

AI_TITLE_PROMPT = """
Your role is to find a title for the conversation.

The title MUST be:
- A sentence, not a question
- A summary of the conversation
- Extremely concise
- If you can't find a title, write "null"
- In the language {language}

User query: {query}

EXAMPLE #1
Human: I want to build an influence strategy on Twitter. Give me a 12-step chart showing how to do it.
AI: Twitter and influence strategy

EXAMPLE #2
Human: aws store api calls for audit
AI: Store AWS API calls

EXAMPLE #3
Human: lol!
AI: A funny conversation

EXAMPLE #4
Human: xxx
AI: null

EXAMPLE #5
Human: hello boy
AI: null

EXAMPLE #6
Human: write a poem
AI: A poem
"""


@api.get(
    "/health/liveness",
    status_code=status.HTTP_204_NO_CONTENT,
    name="Healthckeck liveness",
)
async def health_liveness_get() -> None:
    return None


@api.get(
    "/health/readiness",
    name="Healthckeck readiness",
)
async def health_readiness_get() -> ReadinessModel:
    cache_check, index_check, store_check, stream_check = await asyncio.gather(
        cache.readiness(), index.readiness(), store.readiness(), stream.readiness()
    )

    readiness = ReadinessModel(
        status=ReadinessStatus.OK,
        checks=[
            ReadinessCheckModel(id="cache", status=cache_check),
            ReadinessCheckModel(id="index", status=index_check),
            ReadinessCheckModel(id="startup", status=ReadinessStatus.OK),
            ReadinessCheckModel(id="store", status=store_check),
            ReadinessCheckModel(id="stream", status=stream_check),
        ],
    )

    for check in readiness.checks:
        if check.status != ReadinessStatus.OK:
            readiness.status = ReadinessStatus.FAIL
            break

    return readiness


async def get_current_user(
    token: Annotated[Optional[HTTPAuthorizationCredentials], Depends(auth_scheme)]
) -> UserModel:
    if not token:
        _logger.error("No token provided by Starlette framework")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    jwt = VerifyToken(token.credentials).verify()
    _logger.debug(f"JWT: {jwt}")
    sub = jwt.get("sub")

    if not sub:
        _logger.error("Token does not contain a sub claim")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    email = jwt.get("email")
    name = jwt.get("name")
    preferred_username = jwt.get("preferred_username")
    login_hint = jwt.get("login_hint")

    user = store.user_get(sub)
    if not user:
        user = UserModel(external_id=sub, id=uuid4())
    user_new = user.copy()

    if user.email != email:
        user_new.email = email

    if user.name != name:
        user_new.name = name

    if user.preferred_username != preferred_username:
        user_new.preferred_username = preferred_username

    if user.login_hint != login_hint:
        user_new.login_hint = login_hint

    if user_new != user:
        _logger.debug(f"User {user.id} updated")
        store.user_set(user_new)
        user = user_new

    _logger.info(f"User {user.id} ({user.preferred_username}) logged in")
    _logger.debug(f"JWT: {jwt}")

    return user


@api.get("/prompt")
async def prompt_list() -> ListPromptsModel:
    return ListPromptsModel(prompts=list(AI_PROMPTS.values()))


@api.get("/conversation/{id}")
async def conversation_get(
    id: UUID, current_user: Annotated[UserModel, Depends(get_current_user)]
) -> GetConversationModel:
    conversation = store.conversation_get(id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    messages = store.message_list(conversation.id) or []
    messages.sort(key=lambda x: x.created_at)  # Sort ASC
    return GetConversationModel(
        **conversation.dict(),
        messages=messages,
    )


@api.get("/conversation")
async def conversation_list(
    current_user: Annotated[UserModel, Depends(get_current_user)]
) -> ListConversationsModel:
    conversations = store.conversation_list(current_user.id) or []
    conversations.sort(key=lambda x: x.created_at, reverse=True)  # Sort DESC
    return ListConversationsModel(conversations=conversations)


@api.post(
    "/message",
    description="Moderation check in place, as the content is persisted.",
)
async def message_post(
    content: str,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    language: str,
    secret: bool = False,
    conversation_id: Optional[UUID] = None,
    prompt_id: Optional[UUID] = None,
) -> GetConversationModel:
    # TODO: Moderation fails to test messages longer than 1000 characters approx, that is a huge UX limitation
    # if await content_safety.is_moderated(content):
    #     _logger.info(f"Message content is moderated: {content}")
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Message is moderated",
    #     )

    if conversation_id:
        # Validate API schema
        if prompt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt ID cannot be provided when conversation ID is provided",
            )

        # Validate conversation existence
        _logger.info(
            f"Adding message to conversation (conversation_id={conversation_id})"
        )
        if not store.conversation_exists(conversation_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        # Build message
        message = StoredMessageModel(
            content=content,
            conversation_id=conversation_id,
            role=MessageRole.USER,
            secret=secret,
        )

        # Update conversation
        store.message_set(message)
        conversation = store.conversation_get(conversation_id, current_user.id)
        if not conversation:
            _logger.warn("ACID error: conversation not found after testing existence")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        index.message_index(message)
    else:
        # Test prompt ID if provided
        if prompt_id and prompt_id not in AI_PROMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt ID not found",
            )

        # Build conversation
        conversation = StoredConversationModel(
            prompt=AI_PROMPTS[prompt_id] if prompt_id else None,
            user_id=current_user.id,
        )
        store.conversation_set(conversation)

        # Build message
        message = StoredMessageModel(
            content=content,
            conversation_id=conversation.id,
            role=MessageRole.USER,
            secret=secret,
        )
        store.message_set(message)
        index.message_index(message)

    messages = store.message_list(conversation.id) or []
    messages.sort(key=lambda x: x.created_at)  # Sort ASC

    # Execute message completion in background
    _loop.create_task(
        _generate_completion_background(conversation, messages, current_user, language)
    )

    if conversation.title is None:
        # Execute title completion in background
        _loop.create_task(_guess_title_background(conversation, messages, language))

    return GetConversationModel(
        **conversation.dict(),
        messages=messages,
    )


@api.get(
    "/message/{token}",
    description="Load a message from its token. This endpoint is used for SSE. No authentication is required.",
)
async def message_get(token: UUID, req: Request) -> EventSourceResponse:
    return EventSourceResponse(_read_message_sse(req, token))


async def _read_message_sse(req: Request, message_token: UUID):
    async def clean():
        _logger.info(f"Cleared message cache (message_token={message_token})")
        await stream.clean(message_token)

    async def client_disconnect():
        _logger.info(f"Disconnected from client (via refresh/close) (req={req.client})")
        await clean()

    async def loop_func() -> bool:
        if await req.is_disconnected():
            await client_disconnect()
            return True
        return False

    try:
        async for data in stream.get(message_token, loop_func):
            yield data
    except Exception:
        _logger.exception("Error while streaming message", exc_info=True)
        await clean()


@api.get(
    "/message",
    description="No moderation check, as the content is not stored. Return the 25 most useful messages for the query.",
)
async def message_search(
    q: str, current_user: Annotated[UserModel, Depends(get_current_user)]
) -> SearchModel[MessageModel]:
    messages = index.message_search(q, current_user.id, 25)
    messages.answers.sort(key=lambda x: x.score, reverse=True)  # Sort DESC
    return messages


async def _generate_completion_background(
    conversation: StoredConversationModel,
    messages: List[MessageModel],
    current_user: UserModel,
    language: str,
) -> None:
    _logger.info(f"Getting completion for conversation {conversation.id}")

    last_message = messages[-1]

    if not last_message.token:
        _logger.error("No token provided")
        return

    messages = []

    def on_message(message: StreamMessageModel) -> None:
        _logger.debug(f"Completion result: {message}")
        # Add content to the redis stream cache_key
        stream.push(message.json(), last_message.token)
        messages.append(message)

    def on_usage(total_tokens: int, model_name: str) -> None:
        usage = UsageModel(
            ai_model=model_name,
            conversation_id=conversation.id,
            prompt_name=conversation.prompt.name if conversation.prompt else None,
            tokens=total_tokens,
            user_id=conversation.user_id,
        )
        store.usage_set(usage)

    await openai.chain(
        last_message, conversation, current_user, language, on_message, on_usage
    )

    _logger.debug(f"Final completion results: {messages}")

    # First, store the updated conversation
    res_message = StoredMessageModel(
        actions=list(set([m.action for m in messages if m.action])),
        content="".join([m.content for m in messages if m.content]),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        secret=last_message.secret,
    )
    store.message_set(res_message)
    index.message_index(res_message)

    # Then, send the end of stream message
    stream.end(last_message.token)


async def _guess_title_background(
    conversation: StoredConversationModel,
    messages: List[MessageModel],
    language: str,
) -> None:
    _logger.info(f"Guessing title for conversation {conversation.id}")

    last_message = messages[-1]

    def new_message(message: str) -> None:
        if message == "null":
            _logger.error("No title found")
            return
        # Store the updated conversation
        _logger.debug(f"Title found: {message}")
        conversation.title = message
        store.conversation_set(conversation)

    def usage(total_tokens: int, model_name: str) -> None:
        usage = UsageModel(
            ai_model=model_name,
            conversation_id=conversation.id,
            prompt_name=conversation.prompt.name if conversation.prompt else None,
            tokens=total_tokens,
            user_id=conversation.user_id,
        )
        store.usage_set(usage)

    await openai.completion(last_message, AI_TITLE_PROMPT, language, new_message, usage)


# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(api)
