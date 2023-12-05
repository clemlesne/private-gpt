from typing import List
from pydantic import BaseModel, SecretStr


class AzureFormRecognizerModel(BaseModel):
    api_base: str
    api_token: SecretStr


class BingModel(BaseModel):
    search_url: str
    subscription_key: SecretStr


class TmdbModel(BaseModel):
    bearer_token: SecretStr


class NewsModel(BaseModel):
    api_key: SecretStr


class ListenNotesModel(BaseModel):
    api_key: SecretStr


class OpenWeatherMapModel(BaseModel):
    api_key: SecretStr


class GooglePlacesModel(BaseModel):
    api_key: SecretStr


class AzureCognitiveSearchModel(BaseModel):
    api_key: SecretStr
    displayed_name: str
    index_name: str
    language: str
    semantic_configuration: str
    service_name: str
    top_k: int
    usage: str


class ToolsModel(BaseModel):
    azure_cognitive_search: List[AzureCognitiveSearchModel]
    azure_form_recognizer: AzureFormRecognizerModel
    bing: BingModel
    google_places: GooglePlacesModel
    listen_notes: ListenNotesModel
    news: NewsModel
    open_weather_map: OpenWeatherMapModel
    tmdb: TmdbModel
