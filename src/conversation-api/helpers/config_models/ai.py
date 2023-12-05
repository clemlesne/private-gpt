from pydantic import BaseModel, HttpUrl, SecretStr


class AzureContentSafetyModel(BaseModel):
    api_base: HttpUrl
    api_token: SecretStr
    max_input_str: int


class OpenAiModel(BaseModel):
    ada_deployment: str
    ada_max_input_tokens: int
    ada_model: str
    endpoint: HttpUrl
    gpt_deployment: str
    gpt_max_input_tokens: int
    gpt_model: str


class AiModel(BaseModel):
    azure_content_safety: AzureContentSafetyModel
    openai: OpenAiModel
