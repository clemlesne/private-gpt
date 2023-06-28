# Init environment variables
from typing import Optional
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


# Import modules
import azure.ai.contentsafety as azure_cs
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from datetime import datetime
from fastapi import (
    FastAPI,
    HTTPException,
    status,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from models.message import MessageModel, MessageRole
from models.conversation import ConversationModel, SearchConversationModel
from redis import Redis
from sse_starlette.sse import EventSourceResponse
from tenacity import retry, stop_after_attempt
from uuid import UUID
from pydantic import ValidationError
from yarl import URL
import asyncio
import azure.core.exceptions as azure_exceptions
import logging
import openai
import os
from uuid import uuid4


###
# Init misc
###

VERSION = os.environ.get("VERSION")

###
# Init logging
###

LOGGING_SYS_LEVEL = os.environ.get("MS_LOGGING_SYS_LEVEL", logging.WARN)
logging.basicConfig(level=LOGGING_SYS_LEVEL)

LOGGING_APP_LEVEL = os.environ.get("MS_LOGGING_APP_LEVEL", logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_APP_LEVEL)

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
        logger.info("(OpenAI) Refreshing token")
        oai_cred = DefaultAzureCredential()
        oai_token = oai_cred.get_token("https://cognitiveservices.azure.com/.default")
        openai.api_key = oai_token.token
        # Execute every 20 minutes
        await asyncio.sleep(15*60)


OAI_COMPLETION_ARGS = {
    "deployment_id": os.environ.get("MS_OAI_GPT_DEPLOY_ID"),
    "model": "gpt-3.5-turbo",
}

logger.info(f"(OpenAI) Using Aure private service ({openai.api_base})")
openai.api_type = "azure_ad"
openai.api_version = "2023-05-15"
asyncio.create_task(refresh_oai_token())

###
# Init Azure Content Safety
###

# Score are following: 0 - Safe, 2 - Low, 4 - Medium, 6 - High
# See: https://review.learn.microsoft.com/en-us/azure/cognitive-services/content-safety/concepts/harm-categories?branch=release-build-content-safety#severity-levels
ACS_SEVERITY_THRESHOLD = 2
ACS_API_BASE = os.environ.get("MS_ACS_API_BASE")
ACS_API_TOKEN = os.environ.get("MS_ACS_API_TOKEN")
logger.info(f"(Azure Content Safety) Using Aure private service ({ACS_API_BASE})")
acs_client = azure_cs.ContentSafetyClient(
    ACS_API_BASE, AzureKeyCredential(ACS_API_TOKEN)
)

###
# Init FastAPI
###

ROOT_PATH = os.environ.get("MS_ROOT_PATH", "")
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

# Setup CORS
api.add_middleware(
    CORSMiddleware,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"],
)

###
# Init Redis
###

GLOBAL_CACHE_TTL_SECS = 60 * 60  # 1 hour
REDIS_HOST = os.environ.get("MS_REDIS_HOST")
REDIS_PORT = 6379
REDIS_STREAM_STOPWORD = "STOP"
REDIS_CONVERSATION_PREFIX = "conversation"
REDIS_MESSAGE_PREFIX = "message"
redis_client_api = Redis(db=0, host=REDIS_HOST, port=REDIS_PORT)

###
# Init Generative AI
###

AI_SYS_CONVERSATION_PROMPT = f"""
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
- Write your answer in English
"""

AI_SYS_TITLE_PROMPT = """
Your role is to find a title for the conversation.

The title MUST be:
- A sentence, not a question
- A summary of the conversation
- Extremely concise
- In English
- Not prefixed with "Title: ", etc.
- Shorter than 10 words
"""

@api.get(
    "/health/liveness",
    status_code=status.HTTP_204_NO_CONTENT,
    name="Healthckeck liveness",
)
async def health_liveness_get() -> None:
    return None


@api.get("/conversation/{id}")
async def conversation_get(id: UUID) -> ConversationModel:
    # Get the conversation from Redis
    conversation_raw = redis_client_api.get(conversation_cache_key(id.hex))
    if not conversation_raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    conversation = ConversationModel.parse_raw(conversation_raw)
    return conversation


@api.get("/conversation")
async def conversation_list() -> SearchConversationModel:
    # Get all conversations from Redis
    conversations_raw = redis_client_api.keys(f"${REDIS_CONVERSATION_PREFIX}:*")

    conversations = []
    for c in conversations_raw:
        try:
            conversation = ConversationModel.parse_raw(redis_client_api.get(c))
            conversations.append(conversation)
        except ValidationError:
            logger.warn(f"Invalid conversation found in Redis: {c}")

    # Sort by created_at desc
    conversations.sort(key=lambda x: x.created_at, reverse=True)

    return SearchConversationModel(conversations=conversations)


@api.post("/message")
async def message_post(content: str, conversation_id: Optional[UUID] = None) -> ConversationModel:
    message = MessageModel(content=content, created_at=datetime.now(), role=MessageRole.USER, id=uuid4())

    if conversation_id:
        logger.info(f"Adding message to conversation (conversation_id={conversation_id})")
        # Get the conversation from Redis
        conversation_raw = redis_client_api.get(conversation_cache_key(conversation_id.hex))
        if not conversation_raw:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        conversation = ConversationModel.parse_raw(conversation_raw)
        # Add the message to the conversation
        conversation.messages.append(message)
        # Update the conversation in Redis
        redis_client_api.set(conversation_cache_key(conversation.id.hex), conversation.json(), ex=GLOBAL_CACHE_TTL_SECS)
    else:
        # Create a new conversation
        conversation = ConversationModel(id=uuid4(), created_at=datetime.now(), messages=[message])
        # Store the conversation in Redis
        redis_client_api.set(conversation_cache_key(conversation.id.hex), conversation.json(), ex=GLOBAL_CACHE_TTL_SECS)

    if conversation.title is None:
        # Guess the title
        asyncio.get_running_loop().run_in_executor(
            None, lambda: guess_title(conversation)
        )

    # Execute the message completion
    asyncio.get_running_loop().run_in_executor(
        None, lambda: completion_from_message(conversation, message_cache_key(message.id.hex))
    )

    return conversation


@api.get("/message/{id}")
async def message_get(id: UUID, req: Request) -> EventSourceResponse:
    cache_key = message_cache_key(id.hex)

    # # Test if message_key is in redis
    # if not redis_client_api.exists(cache_key):
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Message not found",
    #     )

    return EventSourceResponse(read_message_sse(req, cache_key))


async def read_message_sse(req: Request, message_key: str):
    stream_id = 0

    def client_disconnect():
        logger.info(f"Disconnected from client (via refresh/close) (req={req.client})")
        logger.debug("Deleting cache key")
        redis_client_api.delete(message_key)

    try:
        is_end = False

        while True:
            # If client closes connection, stop sending events
            if await req.is_disconnected():
                client_disconnect()
                break

            if is_end:
                break

            # Read the redis stream with key cache_key
            messages_raw = redis_client_api.xread(
                streams={message_key: stream_id}
            )
            message_loop = ""

            if messages_raw:
                for message_content in messages_raw[0][1]:
                    stream_id = message_content[0]

                    try:
                        message = message_content[1][b"message"].decode("utf-8")
                        if message == REDIS_STREAM_STOPWORD:
                            is_end = True
                            break
                        message_loop += message
                    except Exception:
                        logger.exception("Error decoding message", exc_info=True)

                # Send the message to the client after the loop
                if message_loop:
                    logger.debug(f"Sending message: {message_loop}")
                    yield message_loop

            await asyncio.sleep(0.25)

    except asyncio.CancelledError as e:
        client_disconnect()
        raise e

    # Delete the cache key
    logger.debug(f"Deleting cache key {message_key}")
    redis_client_api.delete(message_key)


@retry(stop=stop_after_attempt(3))
def completion_from_message(conversation: ConversationModel, cache_key: str) -> None:
    logger.debug(f"Getting completion for conversation {conversation.id}")

    # Create messages object from conversation
    messages = [{"role": MessageRole.SYSTEM, "content": AI_SYS_CONVERSATION_PROMPT}]
    messages += [{"role": m.role, "content": m.content} for m in conversation.messages]

    try:
        # Use chat completion to get a more natural response and lower the usage cost
        chunks = openai.ChatCompletion.create(
            **OAI_COMPLETION_ARGS,
            messages=messages,
            presence_penalty=1,  # Increase the model's likelihood to talk about new topics
            stream=True,
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
            redis_client_api.xadd(cache_key, {"message": content})
            content_full += content

    logger.debug(f"Completion result: {REDIS_STREAM_STOPWORD}")
    redis_client_api.xadd(cache_key, {"message": REDIS_STREAM_STOPWORD})

    # Store the updated conversation in Redis
    conversation.messages.append(MessageModel(content=content_full, created_at=datetime.now(), role=MessageRole.SYSTEM, id=uuid4()))
    redis_client_api.set(conversation_cache_key(conversation.id.hex), conversation.json(), ex=GLOBAL_CACHE_TTL_SECS)


@retry(stop=stop_after_attempt(3))
def guess_title(conversation: ConversationModel) -> None:
    logger.debug(f"Guessing title for conversation {conversation.id}")

    try:
        # Use chat completion to get a more natural response and lower the usage cost
        completion = openai.ChatCompletion.create(
            **OAI_COMPLETION_ARGS,
            messages=[
                {"role": MessageRole.SYSTEM, "content": AI_SYS_TITLE_PROMPT},
                {"role": conversation.messages[0].role, "content": conversation.messages[0].content},
            ],
            presence_penalty=1,  # Increase the model's likelihood to talk about new topics
        )
    except openai.error.AuthenticationError as e:
        logger.exception(e)
        return

    # Update the conversation title
    content = completion["choices"][0].message.content

    # Store the updated conversation in Redis
    conversation_json = redis_client_api.get(conversation_cache_key(conversation.id.hex))
    if conversation_json is not None:
        conversation = ConversationModel.parse_raw(conversation_json)
    conversation.title = content
    redis_client_api.set(conversation_cache_key(conversation.id.hex), conversation.json(), ex=GLOBAL_CACHE_TTL_SECS)


@retry(stop=stop_after_attempt(3))
async def is_moderated(prompt: str) -> bool:
    logger.debug(f"Checking moderation for text: {prompt}")

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


def conversation_cache_key(str: str) -> str:
    return f"${REDIS_CONVERSATION_PREFIX}:{str}"


def message_cache_key(str: str) -> str:
    return f"${REDIS_MESSAGE_PREFIX}:{str}"
