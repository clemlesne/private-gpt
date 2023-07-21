# Import utils
from utils import build_logger, get_config

# Import misc
from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException, status
from tenacity import retry, stop_after_attempt, wait_random_exponential
import azure.ai.contentsafety as azure_cs
import azure.core.exceptions as azure_exceptions


###
# Init misc
###

logger = build_logger(__name__)

###
# Init Azure Content Safety
###

# Score are following: 0 - Safe, 2 - Low, 4 - Medium, 6 - High
# See: https://review.learn.microsoft.com/en-us/azure/cognitive-services/content-safety/concepts/harm-categories?branch=release-build-content-safety#severity-levels
ACS_SEVERITY_THRESHOLD = 2
ACS_API_BASE = get_config("acs", "api_base", str, required=True)
ACS_API_TOKEN = get_config("acs", "api_token", str, required=True)
ACS_MAX_LENGTH = get_config("acs", "max_length", int, required=True)
acs_client = azure_cs.ContentSafetyClient(
    ACS_API_BASE, AzureKeyCredential(ACS_API_TOKEN)
)


class ContentSafety:
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    async def is_moderated(self, prompt: str) -> bool:
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
