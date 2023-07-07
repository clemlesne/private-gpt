# Import utils
from uuid import UUID
from utils import (build_logger, get_config, hash_token)

# Import misc
from azure.identity import DefaultAzureCredential
from models.user import UserModel
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing import Any, Dict, List, AsyncGenerator, Union
import asyncio
import openai


###
# Init misc
###

logger = build_logger(__name__)
loop = asyncio.get_running_loop()


###
# Init OpenIA
###

async def refresh_oai_token_background():
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


openai.api_base = get_config("openai", "api_base", str, required=True)
openai.api_type = "azure_ad"
openai.api_version = "2023-05-15"
logger.info(f"Using Aure private service ({openai.api_base})")
loop.create_task(refresh_oai_token_background())

OAI_GPT_DEPLOY_ID = get_config("openai", "gpt_deploy_id", str, required=True)
OAI_GPT_MAX_TOKENS = get_config("openai", "gpt_max_tokens", int, required=True)
OAI_GPT_MODEL = get_config(
    "openai", "gpt_model", str, default="gpt-3.5-turbo", required=True
)
logger.info(
    f'Using OpenAI ADA model "{OAI_GPT_MODEL}" ({OAI_GPT_DEPLOY_ID}) with {OAI_GPT_MAX_TOKENS} tokens max'
)

OAI_ADA_DEPLOY_ID = get_config("openai", "ada_deploy_id", str, required=True)
OAI_ADA_MAX_TOKENS = get_config("openai", "ada_max_tokens", int, required=True)
OAI_ADA_MODEL = get_config(
    "openai", "ada_model", str, default="text-embedding-ada-002", required=True
)
logger.info(
    f'Using OpenAI ADA model "{OAI_ADA_MODEL}" ({OAI_ADA_DEPLOY_ID}) with {OAI_ADA_MAX_TOKENS} tokens max'
)


class OpenAI:
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    async def vector_from_text(self, prompt: str, user_id: UUID) -> List[float]:
        logger.debug(f"Getting vector for text: {prompt}")
        try:
            res = openai.Embedding.create(
                deployment_id=OAI_ADA_DEPLOY_ID,
                input=prompt,
                model=OAI_ADA_MODEL,
                user=user_id.hex,
            )
        except openai.error.AuthenticationError as e:
            logger.exception(e)
            return []

        return res.data[0].embedding

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    async def completion(self, messages: List[Dict[str, str]], current_user: UserModel) -> Union[str, None]:
        try:
            # Use chat completion to get a more natural response and lower the usage cost
            completion = openai.ChatCompletion.create(
                deployment_id=OAI_GPT_DEPLOY_ID,
                messages=messages,
                model=OAI_GPT_MODEL,
                presence_penalty=1,  # Increase the model's likelihood to talk about new topics
                user=hash_token(current_user.id.bytes).hex,
            )
            content = completion["choices"][0].message.content
        except openai.error.AuthenticationError as e:
            logger.exception(e)
            return

        return content

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    async def completion_stream(self, messages: List[Dict[str, str]], current_user: UserModel) -> AsyncGenerator[Any, None]:
        try:
            # Use chat completion to get a more natural response and lower the usage cost
            chunks = openai.ChatCompletion.create(
                deployment_id=OAI_GPT_DEPLOY_ID,
                messages=messages,
                model=OAI_GPT_MODEL,
                presence_penalty=1,  # Increase the model's likelihood to talk about new topics
                stream=True,
                user=hash_token(current_user.id.bytes).hex,
            )
        except openai.error.AuthenticationError as e:
            logger.exception(e)
            return

        for chunk in chunks:
            content = chunk["choices"][0].get("delta", {}).get("content")
            if content is not None:
                yield content
