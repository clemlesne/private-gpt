# Import utils
from utils import (
    VerifyToken,
    build_logger,
    VERSION,
    hash_token,
    get_config,
    oai_tokens_nb,
)

# Import misc
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.conversation import (
    GetConversationModel,
    ListConversationsModel,
    StoredConversationModel,
)
from models.message import MessageModel, MessageRole
from models.prompt import StoredPromptModel, ListPromptsModel
from models.search import SearchModel
from models.user import UserModel
from persistence.qdrant import QdrantSearch
from persistence.redis import RedisStore, RedisStream, STREAM_STOPWORD
from sse_starlette.sse import EventSourceResponse
from tenacity import retry, stop_after_attempt
from typing import Annotated, Dict, List, Optional
from uuid import UUID
from uuid import uuid4
import asyncio
import azure.ai.contentsafety as azure_cs
import azure.core.exceptions as azure_exceptions
import csv
import openai


###
# Init misc
###

logger = build_logger(__name__)

###
# Init Redis
###

store = RedisStore()
stream = RedisStream()
index = QdrantSearch(store)

###
# Init OpenAI
###


async def refresh_oai_token():
    """
    Refresh OpenAI token every 15 minutes.

    The OpenAI SDK does not support token refresh, so we need to do it manually. We passe manually the token to the SDK. Azure AD tokens are valid for 30 mins, but we refresh every 15 minutes to be safe.

    See: https://github.com/openai/openai-python/pull/350#issuecomment-1489813285
    """
    while True:
        logger.info("Refreshing OpenAI token")
        oai_cred = DefaultAzureCredential()
        oai_token = oai_cred.get_token("https://cognitiveservices.azure.com/.default")
        openai.api_key = oai_token.token
        # Execute every 20 minutes
        await asyncio.sleep(15 * 60)


OAI_GPT_DEPLOY_ID = get_config("openai", "gpt_deploy_id", str, required=True)
OAI_GPT_MAX_TOKENS = get_config("openai", "gpt_max_tokens", int, required=True)
OAI_GPT_MODEL = get_config(
    "openai", "gpt_model", str, default="gpt-3.5-turbo", required=True
)
logger.info(
    f'Using OpenAI ADA model "{OAI_GPT_MODEL}" ({OAI_GPT_DEPLOY_ID}) with {OAI_GPT_MAX_TOKENS} tokens max'
)

openai.api_base = get_config("openai", "api_base", str, required=True)
openai.api_type = "azure_ad"
openai.api_version = "2023-05-15"
logger.info(f"Using Aure private service ({openai.api_base})")
asyncio.create_task(refresh_oai_token())

###
# Init Azure Content Safety
###

# Score are following: 0 - Safe, 2 - Low, 4 - Medium, 6 - High
# See: https://review.learn.microsoft.com/en-us/azure/cognitive-services/content-safety/concepts/harm-categories?branch=release-build-content-safety#severity-levels
ACS_SEVERITY_THRESHOLD = 2
ACS_API_BASE = get_config("acs", "api_base", str, required=True)
ACS_API_TOKEN = get_config("acs", "api_token", str, required=True)
ACS_MAX_LENGTH = get_config("acs", "max_length", int, required=True)
logger.info(f"Connected Azure Content Safety to {ACS_API_BASE}")
acs_client = azure_cs.ContentSafetyClient(
    ACS_API_BASE, AzureKeyCredential(ACS_API_TOKEN)
)

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
        "url": "https://github.com/clemlesne/private-gpt/blob/master/LICENCE",
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

AI_CONVERSATION_DEFAULT_PROMPT = f"""
Today, we are the {datetime.now()}.

You MUST:
- Cite sources and examples as footnotes (example: [^1])
- Write emojis as gemoji shortcodes (example: :smile:)
- Write links with Markdown syntax (example: [You can find it at google.com.](https://google.com))
- Write lists with Markdown syntax, using dashes (example: - First item) or numbers (example: 1. First item)
- Write your answer in the language of the conversation

EXAMPLE #1
User: What is the capital of France?
Paris[^1] is the capital of France.
[^1]: https://paris.fr

EXAMPLE #2
User: I am happy!
:smile:
"""

AI_TITLE_PROMPT = """
Your role is to find a title for the conversation.

The title MUST be:
- A sentence, not a question
- A summary of the conversation
- Extremely concise
- In the language of the conversation
- Shorter than 10 words

Exmaple to follow:

EXAMPLE #1
User: I want to build an influence strategy on Twitter. Give me a 12-step chart showing how to do it.
Twitter and influence strategy

EXAMPLE #2
User: aws store api calls for audit
Store AWS API calls

EXAMPLE #3
User: lol!
A funny conversation

EXAMPLE #4
User: xxx
Unknown subject

EXAMPLE #5
User: hello boy
Unknown subject

EXAMPLE #6
User: write a poem
A poem
"""


@api.get(
    "/health/liveness",
    status_code=status.HTTP_204_NO_CONTENT,
    name="Healthckeck liveness",
)
async def health_liveness_get() -> None:
    return None


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
    logger.info(f"User logged in: {user}")
    logger.debug(f"JWT: {jwt}")
    if user:
        return user

    user = UserModel(external_id=sub, id=uuid4())
    store.user_set(user)
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
    if await is_moderated(content):
        logger.info(f"Message content is moderated: {content}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is moderated",
        )

    message = MessageModel(
        content=content,
        created_at=datetime.now(),
        id=uuid4(),
        role=MessageRole.USER,
        secret=secret,
        token=uuid4(),
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

        # Validate message length
        tokens_nb = oai_tokens_nb(
            message.content
            + "".join([m.content for m in store.message_list(conversation_id)]),
            OAI_GPT_MODEL,
        )
        logger.debug(f"{tokens_nb} tokens in the conversation")
        if tokens_nb > OAI_GPT_MAX_TOKENS:
            logger.info(f"Message ({tokens_nb}) too long for conversation")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation history is too long",
            )

        # Update conversation
        store.message_set(message, conversation_id)
        index.message_index(message, conversation_id, current_user.id)
        conversation = store.conversation_get(conversation_id, current_user.id)
        if not conversation:
            logger.warn("ACID error: conversation not found after testing existence")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        # Test prompt ID if provided
        if prompt_id and prompt_id not in AI_PROMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt ID not found",
            )

        # Validate message length
        tokens_nb = oai_tokens_nb(message.content, OAI_GPT_MODEL)
        logger.debug(f"{tokens_nb} tokens in the conversation")
        if tokens_nb > OAI_GPT_MAX_TOKENS:
            logger.info(f"Message ({tokens_nb}) too long for conversation")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation history is too long",
            )

        # Create a new conversation
        conversation = StoredConversationModel(
            created_at=datetime.now(),
            id=uuid4(),
            prompt=AI_PROMPTS[prompt_id] if prompt_id else None,
            user_id=current_user.id,
        )
        store.conversation_set(conversation)
        store.message_set(message, conversation.id)
        index.message_index(message, conversation.id, current_user.id)

    messages = store.message_list(conversation.id)

    if conversation.title is None:
        asyncio.get_running_loop().run_in_executor(
            None, lambda: guess_title(conversation, messages, current_user)
        )

    # Execute the message completion
    asyncio.get_running_loop().run_in_executor(
        None, lambda: completion_from_conversation(conversation, messages, current_user)
    )

    return GetConversationModel(
        **conversation.dict(),
        messages=messages,
    )


@api.get("/message/{id}")
async def message_get(id: UUID, token: UUID, req: Request) -> EventSourceResponse:
    return EventSourceResponse(read_message_sse(req, token))


async def read_message_sse(req: Request, message_id: UUID):
    def clean():
        logger.info(f"Cleared message cache (message_id={message_id})")
        stream.clean(message_id)

    def client_disconnect():
        logger.info(f"Disconnected from client (via refresh/close) (req={req.client})")
        clean()

    async def loop_func() -> bool:
        if await req.is_disconnected():
            client_disconnect()
            return True
        return False

    try:
        async for data in stream.get(message_id, loop_func):
            yield data
    except Exception:
        logger.exception("Error while streaming message", exc_info=True)
        clean()


@api.get("/message", description="No moderation check, as the content is not stored.")
async def message_search(
    q: str, current_user: Annotated[UserModel, Depends(get_current_user)]
) -> SearchModel:
    return index.message_search(q, current_user.id)


@retry(reraise=True, stop=stop_after_attempt(3))
def completion_from_conversation(
    conversation: StoredConversationModel,
    messages: List[MessageModel],
    current_user: UserModel,
) -> None:
    logger.info(f"Getting completion for conversation {conversation.id}")

    last_message = messages[-1]

    if not last_message.token:
        logger.error("No token provided")
        return

    # Create messages object from conversation
    completion_messages = [
        {"role": MessageRole.SYSTEM, "content": AI_CONVERSATION_DEFAULT_PROMPT}
    ]
    if conversation.prompt:
        completion_messages += [
            {"role": MessageRole.SYSTEM, "content": conversation.prompt.content}
        ]
    completion_messages += [{"role": m.role, "content": m.content} for m in messages]

    logger.debug(f"Completion messages: {completion_messages}")

    try:
        # Use chat completion to get a more natural response and lower the usage cost
        chunks = openai.ChatCompletion.create(
            deployment_id=OAI_GPT_DEPLOY_ID,
            messages=completion_messages,
            model=OAI_GPT_MODEL,
            presence_penalty=1,  # Increase the model's likelihood to talk about new topics
            stream=True,
            user=hash_token(current_user.id.bytes).hex,
        )
    except openai.error.AuthenticationError as e:
        logger.exception(e)
        return

    content_full = ""
    for chunk in chunks:
        content = chunk["choices"][0].get("delta", {}).get("content")
        if content is not None:
            logger.debug(f"Completion result: {content}")
            # Add content to the redis stream cache_key
            stream.push(content, last_message.token)
            content_full += content

    # First, store the updated conversation in Redis
    res_message = MessageModel(
        content=content_full,
        created_at=datetime.now(),
        id=uuid4(),
        role=MessageRole.ASSISTANT,
        secret=last_message.secret,
    )
    store.message_set(res_message, conversation.id)
    index.message_index(res_message, conversation.id, current_user.id)

    # Then, send the end of stream message
    stream.push(STREAM_STOPWORD, last_message.token)


@retry(reraise=True, stop=stop_after_attempt(3))
def guess_title(
    conversation: StoredConversationModel,
    messages: List[MessageModel],
    current_user: UserModel,
) -> None:
    logger.info(f"Guessing title for conversation {conversation.id}")

    # Create messages object from conversation
    # We don't include the custom prompt, as it will false the title response (espacially with ASCI art prompt)
    completion_messages = [
        {"role": MessageRole.SYSTEM, "content": AI_CONVERSATION_DEFAULT_PROMPT}
    ]
    completion_messages += [{"role": m.role, "content": m.content} for m in messages]

    logger.debug(f"Completion messages: {completion_messages}")

    try:
        # Use chat completion to get a more natural response and lower the usage cost
        completion = openai.ChatCompletion.create(
            deployment_id=OAI_GPT_DEPLOY_ID,
            messages=completion_messages,
            model=OAI_GPT_MODEL,
            presence_penalty=1,  # Increase the model's likelihood to talk about new topics
            user=hash_token(current_user.id.bytes).hex,
        )
        content = completion["choices"][0].message.content
    except openai.error.AuthenticationError as e:
        logger.exception(e)
        return

    # Store the updated conversation in Redis
    conversation.title = content
    store.conversation_set(conversation)


@retry(reraise=True, stop=stop_after_attempt(3))
async def is_moderated(prompt: str) -> bool:
    logger.debug(f"Checking moderation for text: {prompt}")

    if len(prompt) > ACS_MAX_LENGTH:
        logger.info(f"Message ({len(prompt)}) too long for moderation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message too long",
        )

    req = azure_cs.models.AnalyzeTextOptions(
        text=prompt,
        categories=[
            azure_cs.models.TextCategory.HATE,
            azure_cs.models.TextCategory.SELF_HARM,
            azure_cs.models.TextCategory.SEXUAL,
            azure_cs.models.TextCategory.VIOLENCE,
        ],
    )

    try:
        res = acs_client.analyze_text(req)
    except azure_exceptions.ClientAuthenticationError as e:
        logger.exception(e)
        return False

    is_moderated = any(
        cat.severity >= ACS_SEVERITY_THRESHOLD
        for cat in [
            res.hate_result,
            res.self_harm_result,
            res.sexual_result,
            res.violence_result,
        ]
    )
    if is_moderated:
        logger.info(f"Message is moderated: {prompt}")
        logger.debug(f"Moderation result: {res}")

    return is_moderated
