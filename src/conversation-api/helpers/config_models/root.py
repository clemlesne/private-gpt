from helpers.config_models.ai import AiModel
from helpers.config_models.api import ApiModel
from helpers.config_models.monitoring import MonitoringModel
from helpers.config_models.oidc import OidcModel
from helpers.config_models.persistence import PersistenceModel
from helpers.config_models.tools import ToolsModel
from pydantic import BaseModel


class RootModel(BaseModel):
    ai: AiModel
    api: ApiModel
    monitoring: MonitoringModel
    oidc: OidcModel
    persistence: PersistenceModel
    tools: ToolsModel
