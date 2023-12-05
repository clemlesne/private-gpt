from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException, status
from helpers.config import CONFIG
from helpers.logging import build_logger
from tenacity import retry, stop_after_attempt, wait_random_exponential
import azure.ai.contentsafety as azure_cs
import azure.core.exceptions as azure_exceptions


_logger = build_logger(__name__)


# Score are following: 0 - Safe, 2 - Low, 4 - Medium, 6 - High
# See: https://review.learn.microsoft.com/en-us/azure/cognitive-services/content-safety/concepts/harm-categories?branch=release-build-content-safety#severity-levels
ACS_SEVERITY_THRESHOLD = 2
acs_client = azure_cs.ContentSafetyClient(
    credential=AzureKeyCredential(
        CONFIG.ai.azure_content_safety.api_token.get_secret_value()
    ),
    endpoint=str(CONFIG.ai.azure_content_safety.api_base),
)


class ContentSafety:
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.5, max=30),
    )
    async def is_moderated(self, prompt: str) -> bool:
        _logger.debug(f"Checking moderation for text: {prompt}")

        if len(prompt) > CONFIG.ai.azure_content_safety.max_input_str:
            _logger.info(f"Message ({len(prompt)}) too long for moderation")
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
            _logger.exception(e)
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
            _logger.info(f"Message is moderated: {prompt}")
            _logger.debug(f"Moderation result: {res}")

        return is_moderated
