# Import utils
from utils import VerifyToken, build_logger, VERSION

# Import misc
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.conversation import GetConversationModel, SearchConversationModel
from models.message import MessageModel, MessageRole
from models.search import SearchModel
from models.user import UserModel
from persistence.qdrant import QdrantSearch
from persistence.redis import RedisStore, RedisStream, STREAM_STOPWORD
from sse_starlette.sse import EventSourceResponse
from tenacity import retry, stop_after_attempt
from typing import Annotated, Optional
from uuid import UUID
from uuid import uuid4
import asyncio
import azure.ai.contentsafety as azure_cs
import azure.core.exceptions as azure_exceptions
import openai
import os
import time


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


OAI_COMPLETION_ARGS = {
    "deployment_id": os.environ.get("PG_OAI_GPT_DEPLOY_ID"),
    "model": "gpt-3.5-turbo",
}

logger.info(f"Using Aure private service ({openai.api_base})")
openai.api_type = "azure_ad"
openai.api_version = "2023-05-15"
asyncio.create_task(refresh_oai_token())

###
# Init Azure Content Safety
###

# Score are following: 0 - Safe, 2 - Low, 4 - Medium, 6 - High
# See: https://review.learn.microsoft.com/en-us/azure/cognitive-services/content-safety/concepts/harm-categories?branch=release-build-content-safety#severity-levels
ACS_SEVERITY_THRESHOLD = 2
ACS_API_BASE = os.environ.get("PG_ACS_API_BASE")
ACS_API_TOKEN = os.environ.get("PG_ACS_API_TOKEN")
logger.info(f"Connected Azure Content Safety to {ACS_API_BASE}")
acs_client = azure_cs.ContentSafetyClient(
    ACS_API_BASE, AzureKeyCredential(ACS_API_TOKEN)
)

###
# Init FastAPI
###

ROOT_PATH = os.environ.get("PG_ROOT_PATH", "")
logger.info(f'Using root path: "{ROOT_PATH}"')

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

AI_CONVERSATION_PROMPT = f"""
You are a assistant at the need of the user. You are here to help them. You are an AI, not a human.

Today, we are the {datetime.now()}.

You MUST:
- Be concise and precise
- Be kind and respectful
- If you don't know, don't answer
- Limit your answer few sentences
- Not talk about politics, religion, or any other sensitive topic
- Write links with Markdown syntax (example: [You can find it at google.com.](https://google.com))
- Write lists with Markdown syntax, using dashes (example: - First item) or numbers (example: 1. First item)
- Write your answer in the language of the conversation
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


async def get_current_user(token: Annotated[Optional[HTTPAuthorizationCredentials], Depends(auth_scheme)]) -> UserModel:
    if not token:
        logger.error("No token provided by Starlette framework")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    jwt = VerifyToken(token.credentials).verify()
    sub = jwt.get("sub")

    if not sub:
        logger.error("Token does not contain a sub claim")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.info(f"User {sub} logged in")
    logger.debug(jwt)

    user = store.user_get(sub)
    if user:
        return user

    user = UserModel(external_id=sub, id=uuid4())
    store.user_set(user)
    return user


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
    return conversation


@api.get("/conversation")
async def conversation_list(
    current_user: Annotated[UserModel, Depends(get_current_user)]
) -> SearchConversationModel:
    conversations = store.conversation_list(current_user.id)
    return SearchConversationModel(conversations=conversations)


@api.post("/message")
async def message_post(
    content: str,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    conversation_id: Optional[UUID] = None,
) -> GetConversationModel:
    message = MessageModel(
        content=content,
        created_at=datetime.now(),
        role=MessageRole.USER,
        id=uuid4(),
        token=uuid4(),
    )

    if conversation_id:
        logger.info(
            f"Adding message to conversation (conversation_id={conversation_id})"
        )
        if not store.conversation_exists(conversation_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
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
        conversation = GetConversationModel(
            id=uuid4(),
            created_at=datetime.now(),
            messages=[message],
            user_id=current_user.id,
        )
        store.conversation_set(conversation)
        store.message_set(message, conversation.id)
        index.message_index(message, conversation.id, current_user.id)

    if conversation.title is None:
        asyncio.get_running_loop().run_in_executor(
            None, lambda: guess_title(conversation, current_user)
        )

    # Execute the message completion
    asyncio.get_running_loop().run_in_executor(
        None, lambda: completion_from_message(conversation, message, current_user)
    )

    return conversation


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


@api.get("/message")
async def message_search(
    q: str, current_user: Annotated[UserModel, Depends(get_current_user)]
) -> SearchModel:
    return index.message_search(q, current_user.id)


@retry(stop=stop_after_attempt(3))
def completion_from_message(
    conversation: GetConversationModel,
    in_message: MessageModel,
    current_user: UserModel,
) -> None:
    logger.info(f"Getting completion for conversation {conversation.id}")

    if not in_message.token:
        logger.error("No token provided")
        return

    # Create messages object from conversation
    completion_messages = [
        {"role": MessageRole.SYSTEM, "content": AI_CONVERSATION_PROMPT}
    ]
    completion_messages += [
        {"role": m.role, "content": m.content} for m in conversation.messages
    ]

    try:
        # Use chat completion to get a more natural response and lower the usage cost
        chunks = openai.ChatCompletion.create(
            **OAI_COMPLETION_ARGS,
            messages=completion_messages,
            presence_penalty=1,  # Increase the model's likelihood to talk about new topics
            stream=True,
            user=current_user.id.hex,
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
            stream.push(content, in_message.token)
            content_full += content

    # First, store the updated conversation in Redis
    res_message = MessageModel(
        content=content_full,
        created_at=datetime.now(),
        role=MessageRole.ASSISTANT,
        id=uuid4(),
    )
    store.message_set(res_message, conversation.id)
    index.message_index(res_message, conversation.id, current_user.id)

    # Then, send the end of stream message
    stream.push(STREAM_STOPWORD, in_message.token)


@retry(stop=stop_after_attempt(3))
def guess_title(conversation: GetConversationModel, current_user: UserModel) -> None:
    logger.info(f"Guessing title for conversation {conversation.id}")

    try:
        # Use chat completion to get a more natural response and lower the usage cost
        completion = openai.ChatCompletion.create(
            **OAI_COMPLETION_ARGS,
            messages=[
                {"role": MessageRole.SYSTEM, "content": AI_TITLE_PROMPT},
                {
                    "role": conversation.messages[0].role,
                    "content": conversation.messages[0].content,
                },
            ],
            presence_penalty=1,  # Increase the model's likelihood to talk about new topics
            user=current_user.id.hex,
        )
        content = completion["choices"][0].message.content
    except openai.error.AuthenticationError as e:
        logger.exception(e)
        return

    # Store the updated conversation in Redis
    conversation.title = content
    store.conversation_set(conversation)


@retry(stop=stop_after_attempt(3))
async def is_moderated(prompt: str) -> bool:
    logger.info(f"Checking moderation for text: {prompt}")

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

    logger.debug(f"Moderation result: {res}")
    return any(
        cat.severity >= ACS_SEVERITY_THRESHOLD
        for cat in [
            res.hate_result,
            res.self_harm_result,
            res.sexual_result,
            res.violence_result,
        ]
    )
