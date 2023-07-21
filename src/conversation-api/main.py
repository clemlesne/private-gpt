# Import utils
from utils import (
    build_logger,
    get_config,
    hash_token,
    oai_tokens_nb,
    VerifyToken,
    VERSION,
)

# Import misc
from ai.contentsafety import ContentSafety
from ai.openai import (
    OpenAI,
)
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.conversation import (
    GetConversationModel,
    ListConversationsModel,
    StoredConversationModel,
)
from models.message import MessageModel, MessageRole, StoredMessageModel
from models.prompt import StoredPromptModel, ListPromptsModel
from models.readiness import ReadinessModel, ReadinessCheckModel, ReadinessStatus
from models.search import SearchModel
from models.usage import UsageModel
from models.user import UserModel
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from persistence.isearch import SearchImplementation
from persistence.istore import StoreImplementation
from persistence.istream import StreamImplementation
from sse_starlette.sse import EventSourceResponse
from typing import Annotated, Dict, List, Optional
from uuid import UUID
from uuid import uuid4
import asyncio
import csv


###
# Init misc
###

logger = build_logger(__name__)
loop = asyncio.get_running_loop()

###
# Init persistence
###

store_impl = get_config("persistence", "store", StoreImplementation, required=True)
if store_impl == StoreImplementation.COSMOS:
    logger.info("Using CosmosDB store")
    from persistence.cosmos import CosmosStore

    store = CosmosStore()
elif store_impl == StoreImplementation.REDIS:
    logger.info("Using Redis store")
    from persistence.redis import RedisStore

    store = RedisStore()
else:
    raise ValueError(f"Unknown store implementation: {store_impl}")

###
# Init Generative AI
###

openai = OpenAI(store)
content_safety = ContentSafety()

###
# Init persistence
###

search_impl = get_config("persistence", "search", SearchImplementation, required=True)
if search_impl == SearchImplementation.QDRANT:
    logger.info("Using Qdrant search")
    from persistence.qdrant import QdrantSearch

    index = QdrantSearch(store, openai)
else:
    raise ValueError(f"Unknown search implementation: {search_impl}")

stream_impl = get_config("persistence", "stream", StreamImplementation, required=True)
if stream_impl == StreamImplementation.REDIS:
    logger.info("Using Redis stream")
    from persistence.redis import RedisStream, STREAM_STOPWORD

    stream = RedisStream()
else:
    raise ValueError(f"Unknown stream implementation: {stream_impl}")

###
# Init FastAPI
###

ROOT_PATH = get_config("api", "root_path", str, default="")
logger.info(f'Using root path "{ROOT_PATH}"')

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
    logger.info(f"Loaded {len(prompts)} prompts")
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
- In the language of the conversation

EXAMPLE #1
User: I want to build an influence strategy on Twitter. Give me a 12-step chart showing how to do it.
You: Twitter and influence strategy

EXAMPLE #2
User: aws store api calls for audit
You: Store AWS API calls

EXAMPLE #3
User: lol!
You: A funny conversation

EXAMPLE #4
User: xxx
You: null

EXAMPLE #5
User: hello boy
You: null

EXAMPLE #6
User: write a poem
You: A poem
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
    index_check, store_check, stream_check = await asyncio.gather(
        index.readiness(), store.readiness(), stream.readiness()
    )

    readiness = ReadinessModel(
        status=ReadinessStatus.OK,
        checks=[
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
        logger.error("No token provided by Starlette framework")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    jwt = VerifyToken(token.credentials).verify()
    sub = jwt.get("sub")

    if not sub:
        logger.error("Token does not contain a sub claim")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    user = store.user_get(sub)
    if not user:
        user = UserModel(external_id=sub, id=uuid4())
        store.user_set(user)

    logger.info(f'User "{user.id}" logged in')
    logger.debug(f"JWT: {jwt}")

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
    messages = store.message_list(conversation.id)
    return GetConversationModel(
        **conversation.dict(),
        messages=messages,
    )


@api.get("/conversation")
async def conversation_list(
    current_user: Annotated[UserModel, Depends(get_current_user)]
) -> ListConversationsModel:
    conversations = store.conversation_list(current_user.id)
    return ListConversationsModel(conversations=conversations)


@api.post(
    "/message", description="Moderation check in place, as the content is persisted."
)
async def message_post(
    content: str,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    secret: bool = False,
    conversation_id: Optional[UUID] = None,
    prompt_id: Optional[UUID] = None,
) -> GetConversationModel:
    if await content_safety.is_moderated(content):
        logger.info(f"Message content is moderated: {content}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is moderated",
        )

    if conversation_id:
        # Validate API schema
        if prompt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt ID cannot be provided when conversation ID is provided",
            )

        # Validate conversation existence
        logger.info(
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
            created_at=datetime.utcnow(),
            id=uuid4(),
            role=MessageRole.USER,
            secret=secret,
            token=uuid4(),
        )

        # tokens_nb = await _validate_message_length(message=message)

        # Update conversation
        store.message_set(message)
        conversation = store.conversation_get(conversation_id, current_user.id)
        if not conversation:
            logger.warn("ACID error: conversation not found after testing existence")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        await _message_index(message, current_user, conversation.prompt)

        # # Build usage
        # usage = UsageModel(
        #     ai_model=OAI_GPT_MODEL,
        #     conversation_id=conversation_id,
        #     created_at=datetime.utcnow(),
        #     id=uuid4(),
        #     tokens=tokens_nb,
        #     user_id=current_user.id,
        #     prompt_name=conversation.prompt.name if conversation.prompt else None,
        # )
        # store.usage_set(usage)
    else:
        # Test prompt ID if provided
        if prompt_id and prompt_id not in AI_PROMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt ID not found",
            )

        # tokens_nb = await _validate_message_length(content=content)

        # Build conversation
        conversation = StoredConversationModel(
            created_at=datetime.utcnow(),
            id=uuid4(),
            prompt=AI_PROMPTS[prompt_id] if prompt_id else None,
            user_id=current_user.id,
        )
        store.conversation_set(conversation)

        # # Build usage
        # usage = UsageModel(
        #     ai_model=OAI_GPT_MODEL,
        #     conversation_id=conversation.id,
        #     created_at=datetime.utcnow(),
        #     id=uuid4(),
        #     tokens=tokens_nb,
        #     user_id=current_user.id,
        #     prompt_name=conversation.prompt.name if conversation.prompt else None,
        # )
        # await store.usage_set(usage)

        # Build message
        message = StoredMessageModel(
            content=content,
            conversation_id=conversation.id,
            created_at=datetime.utcnow(),
            id=uuid4(),
            role=MessageRole.USER,
            secret=secret,
            token=uuid4(),
        )
        store.message_set(message)
        await _message_index(message, current_user, conversation.prompt)

    messages = store.message_list(conversation.id)

    if conversation.title is None:
        loop.create_task(_guess_title_background(conversation, messages, current_user))

    # Execute the message completion
    loop.create_task(
        _generate_completion_background(conversation, messages, current_user)
    )

    return GetConversationModel(
        **conversation.dict(),
        messages=messages,
    )


@api.get("/message/{id}")
async def message_get(id: UUID, token: UUID, req: Request) -> EventSourceResponse:
    return EventSourceResponse(_read_message_sse(req, token))


async def _read_message_sse(req: Request, message_id: UUID):
    async def clean():
        logger.info(f"Cleared message cache (message_id={message_id})")
        await stream.clean(message_id)

    async def client_disconnect():
        logger.info(f"Disconnected from client (via refresh/close) (req={req.client})")
        await clean()

    async def loop_func() -> bool:
        if await req.is_disconnected():
            await client_disconnect()
            return True
        return False

    try:
        async for data in stream.get(message_id, loop_func):
            yield data
    except Exception:
        logger.exception("Error while streaming message", exc_info=True)
        await clean()


@api.get(
    "/message",
    description="No moderation check, as the content is not stored. Return the 25 most useful messages for the query.",
)
async def message_search(
    q: str, current_user: Annotated[UserModel, Depends(get_current_user)]
) -> SearchModel:
    return await index.message_search(q, current_user.id, 25)


async def _generate_completion_background(
    conversation: StoredConversationModel,
    messages: List[MessageModel],
    current_user: UserModel,
) -> None:
    logger.info(f"Getting completion for conversation {conversation.id}")

    last_message = messages[-1]

    if not last_message.token:
        logger.error("No token provided")
        return

    content_full = ""
    async for message in openai.chain(last_message, conversation.id, current_user.id):
        logger.debug(f"Completion result: {message}")
        # Add content to the redis stream cache_key
        await stream.push(message, last_message.token)
        content_full += message

    # First, store the updated conversation in Redis
    res_message = StoredMessageModel(
        content=content_full,
        conversation_id=conversation.id,
        created_at=datetime.utcnow(),
        id=uuid4(),
        role=MessageRole.ASSISTANT,
        secret=last_message.secret,
    )
    store.message_set(res_message)
    await _message_index(res_message, current_user, conversation.prompt)

    # Then, send the end of stream message
    await stream.push(STREAM_STOPWORD, last_message.token)


async def _message_index(
    message: StoredMessageModel,
    current_user: UserModel,
    prompt: Optional[StoredPromptModel],
) -> None:
    # tokens_nb = oai_tokens_nb(message.content, OAI_ADA_MODEL)
    # if tokens_nb > OAI_ADA_MAX_TOKENS:
    #     logger.info(f"Message ({tokens_nb}) too long for indexing")
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Conversation history is too long",
    #     )

    # usage = UsageModel(
    #     ai_model=OAI_ADA_MODEL,
    #     conversation_id=message.conversation_id,
    #     created_at=datetime.utcnow(),
    #     id=uuid4(),
    #     tokens=oai_tokens_nb(message.content, OAI_ADA_MODEL),
    #     user_id=current_user.id,
    #     prompt_name=prompt.name if prompt else None,
    # )
    # store.usage_set(usage)
    await index.message_index(message)


# async def _validate_message_length(
#     message: Optional[StoredMessageModel] = None,
#     content: Optional[str] = None,
# ) -> int:
#     if content:
#         tokens_nb = oai_tokens_nb(content, OAI_GPT_MODEL)
#     elif message:
#         tokens_nb = oai_tokens_nb(
#             message.content
#             + "".join(
#                 [m.content for m in store.message_list(message.conversation_id)]
#             ),
#             OAI_GPT_MODEL,
#         )
#     else:
#         raise ValueError(
#             'Either message or content must be provided to "validate_usage"'
#         )

#     logger.debug(f"{tokens_nb} tokens in the conversation")

#     if tokens_nb > OAI_GPT_MAX_TOKENS:
#         logger.info(f"Message ({tokens_nb}) too long for conversation")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Conversation history is too long",
#         )

#     return tokens_nb


async def _guess_title_background(
    conversation: StoredConversationModel,
    messages: List[MessageModel],
    current_user: UserModel,
) -> None:
    logger.info(f"Guessing title for conversation {conversation.id}")

    last_message = messages[-1]

    message = await openai.completion(last_message, conversation.id, current_user.id)

    if message.content == "null":
        logger.error("No title found")
        return

    # Store the updated conversation in Redis
    logger.debug(f"Title found: {message.content}")
    conversation.title = message.content
    store.conversation_set(conversation)


# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(api)
