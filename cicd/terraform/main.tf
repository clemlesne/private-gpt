locals {
  tags = {
    app     = "private-gpt"
    sources = "https://github.com/clemlesne/private-gpt"
  }
}

data "azurerm_client_config" "current" {}

resource "azurerm_user_assigned_identity" "identity" {
  location            = azurerm_resource_group.this.location
  name                = var.resourcePrefix
  resource_group_name = azurerm_resource_group.this.name

  tags = local.tags
}

resource "azuread_application" "this" {
  description      = "Deploy smart and secure conversational agents for your employees, using Azure. Able to use both private and public data."
  display_name     = "${var.endUserAppName} (${var.resourcePrefix})"
  logo_image       = filebase64("${path.root}/../../logo-512.png")
  owners           = [data.azurerm_client_config.current.object_id]
  sign_in_audience = "AzureADandPersonalMicrosoftAccount"
  support_url      = "https://github.com/clemlesne/private-gpt/issues"

  api {
    requested_access_token_version = 2
  }

  single_page_application {
    redirect_uris = ["https://conversation-ui.${azurerm_container_app_environment.this.default_domain}/"]
  }

  web {
    homepage_url = "https://conversation-ui.${azurerm_container_app_environment.this.default_domain}"

    implicit_grant {
      id_token_issuance_enabled = true
    }
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph

    resource_access {
      id   = "14dad69e-099b-42c9-810b-d002981feec1"
      type = "Scope"
    }

    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d"
      type = "Scope"
    }

    resource_access {
      id   = "37f7f235-527c-4136-accd-4a02d197296e"
      type = "Scope"
    }

    resource_access {
      id   = "64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0"
      type = "Scope"
    }
  }
}

resource "azurerm_resource_group" "this" {
  location = var.location
  name     = var.resourcePrefix

  tags = local.tags
}

resource "azurerm_cognitive_account" "form_recognizer" {
  location            = azurerm_resource_group.this.location
  name                = "${var.resourcePrefix}-${azurerm_resource_group.this.location}-form-recognizer"
  resource_group_name = azurerm_resource_group.this.name

  custom_subdomain_name = "${var.resourcePrefix}-${azurerm_resource_group.this.location}-form-recognizer"
  kind                  = "FormRecognizer" # Only one free account is allowed
  sku_name              = "S0"

  tags = local.tags
}

data "azapi_resource" "bing" {
  name      = var.resourcePrefix
  parent_id = azurerm_resource_group.this.id
  type      = "Microsoft.Bing/accounts@2020-06-10"

  response_export_values = ["properties.endpoint"]
}

data "azapi_resource_action" "bing" {
  resource_id = data.azapi_resource.bing.id
  type        = data.azapi_resource.bing.type

  action                 = "listKeys"
  response_export_values = ["*"]
}

resource "azurerm_cognitive_account" "openai" {
  location            = var.openaiLocation != null ? var.openaiLocation : azurerm_resource_group.this.location
  name                = "${var.resourcePrefix}-${var.openaiLocation != null ? var.openaiLocation : azurerm_resource_group.this.location}-openai"
  resource_group_name = azurerm_resource_group.this.name

  custom_subdomain_name = "${var.resourcePrefix}-${var.openaiLocation != null ? var.openaiLocation : azurerm_resource_group.this.location}-openai"
  kind                  = "OpenAI"
  sku_name              = "S0"

  tags = local.tags
}

resource "azurerm_cognitive_deployment" "openai_ada" {
  name = "ada"

  cognitive_account_id   = azurerm_cognitive_account.openai.id
  version_upgrade_option = "NoAutoUpgrade"

  model {
    format  = "OpenAI"
    name    = var.openaiAdaModelName
    version = var.openaiAdaModelVersion
  }

  scale {
    capacity = 50 # In tokens-per-minute
    type     = "Standard"
  }
}

resource "azurerm_cognitive_deployment" "openai_gpt" {
  name = "gpt"

  cognitive_account_id   = azurerm_cognitive_account.openai.id
  version_upgrade_option = "NoAutoUpgrade"

  model {
    format  = "OpenAI"
    name    = var.openaiGptModelName
    version = var.openaiGptModelVersion
  }

  scale {
    capacity = 50 # In tokens-per-minute
    type     = "Standard"
  }
}

resource "azurerm_role_assignment" "openai_contributor" {
  for_each = toset(compact([
    azurerm_container_app.conversation_api.identity[0].principal_id,
    var.selfAccess ? data.azurerm_client_config.current.object_id : null,
  ]))

  principal_id         = each.value
  role_definition_name = "Cognitive Services OpenAI Contributor"
  scope                = azurerm_cognitive_account.openai.id
}

resource "azurerm_cognitive_account" "content_safety" {
  location            = azurerm_resource_group.this.location
  name                = "${var.resourcePrefix}-${azurerm_resource_group.this.location}-content-safety"
  resource_group_name = azurerm_resource_group.this.name

  custom_subdomain_name = "${var.resourcePrefix}-${azurerm_resource_group.this.location}-content-safety"
  kind                  = "ContentModerator"
  sku_name              = "S0"

  tags = local.tags
}

resource "azurerm_redis_cache" "this" {
  location            = azurerm_resource_group.this.location
  name                = var.resourcePrefix
  resource_group_name = azurerm_resource_group.this.name

  capacity = 0
  family   = "C"
  sku_name = "Basic"

  tags = local.tags
}

resource "azurerm_cosmosdb_account" "this" {
  location            = azurerm_resource_group.this.location
  name                = var.resourcePrefix
  resource_group_name = azurerm_resource_group.this.name

  local_authentication_disabled = true
  offer_type                    = "Standard"

  consistency_policy {
    consistency_level = "ConsistentPrefix"
  }

  capabilities {
    name = "EnableServerless"
  }

  geo_location {
    location          = azurerm_resource_group.this.location
    failover_priority = 0
  }

  tags = local.tags
}

resource "azurerm_cosmosdb_sql_database" "this" {
  account_name        = azurerm_cosmosdb_account.this.name
  name                = "db"
  resource_group_name = azurerm_resource_group.this.name
}

resource "azurerm_cosmosdb_sql_container" "conversation" {
  account_name        = azurerm_cosmosdb_account.this.name
  database_name       = azurerm_cosmosdb_sql_database.this.name
  name                = "conversation"
  resource_group_name = azurerm_resource_group.this.name

  partition_key_path = "/user_id"
}

resource "azurerm_cosmosdb_sql_container" "message" {
  account_name        = azurerm_cosmosdb_account.this.name
  database_name       = azurerm_cosmosdb_sql_database.this.name
  name                = "message"
  resource_group_name = azurerm_resource_group.this.name

  partition_key_path = "/conversation_id"
}

resource "azurerm_cosmosdb_sql_container" "usage" {
  account_name        = azurerm_cosmosdb_account.this.name
  database_name       = azurerm_cosmosdb_sql_database.this.name
  name                = "usage"
  resource_group_name = azurerm_resource_group.this.name

  partition_key_path = "/user_id"
}

resource "azurerm_cosmosdb_sql_container" "user" {
  account_name        = azurerm_cosmosdb_account.this.name
  database_name       = azurerm_cosmosdb_sql_database.this.name
  name                = "user"
  resource_group_name = azurerm_resource_group.this.name

  partition_key_path = "/dummy"
}

// Using built-in role definition
// See: https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac#built-in-role-definitions
data "azurerm_cosmosdb_sql_role_definition" "data_contributor" {
  account_name        = azurerm_cosmosdb_account.this.name
  resource_group_name = azurerm_resource_group.this.name
  role_definition_id  = "00000000-0000-0000-0000-000000000002"
}

resource "azurerm_cosmosdb_sql_role_assignment" "this" {
  account_name        = azurerm_cosmosdb_account.this.name
  resource_group_name = azurerm_resource_group.this.name
  scope               = azurerm_cosmosdb_account.this.id

  principal_id       = azurerm_container_app.conversation_api.identity[0].principal_id
  role_definition_id = data.azurerm_cosmosdb_sql_role_definition.data_contributor.id
}

resource "azurerm_log_analytics_workspace" "this" {
  location            = azurerm_resource_group.this.location
  name                = var.resourcePrefix
  resource_group_name = azurerm_resource_group.this.name

  retention_in_days = 30
  sku               = "PerGB2018"

  tags = local.tags
}

resource "azurerm_application_insights" "this" {
  location            = azurerm_resource_group.this.location
  name                = var.resourcePrefix
  resource_group_name = azurerm_resource_group.this.name

  application_type = "web"
  workspace_id     = azurerm_log_analytics_workspace.this.id

  tags = local.tags
}

resource "azurerm_role_assignment" "application_insights_contributor" {
  for_each = toset(compact([
    azurerm_container_app.conversation_api.identity[0].principal_id,
    var.selfAccess ? data.azurerm_client_config.current.object_id : null,
  ]))

  principal_id         = each.value
  role_definition_name = "Monitoring Metrics Publisher"
  scope                = azurerm_application_insights.this.id
}

resource "azurerm_container_app_environment" "this" {
  location            = azurerm_resource_group.this.location
  name                = var.resourcePrefix
  resource_group_name = azurerm_resource_group.this.name

  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  tags = local.tags
}

resource "azurerm_container_app" "conversation_ui" {
  container_app_environment_id = azurerm_container_app_environment.this.id
  name                         = "conversation-ui"
  resource_group_name          = azurerm_resource_group.this.name

  revision_mode = "Single"

  template {
    container {
      cpu    = 0.25
      image  = "ghcr.io/clemlesne/private-gpt:conversation-ui-${var.appVersion}"
      memory = "0.5Gi"
      name   = "conversation-ui"

      liveness_probe {
        failure_count_threshold = 6
        interval_seconds        = 5
        path                    = "/health/liveness"
        port                    = 8080
        timeout                 = 5
        transport               = "HTTP"
      }

      startup_probe {
        failure_count_threshold = 10
        interval_seconds        = 5
        port                    = 8080
        transport               = "TCP"
        timeout                 = 5
      }

      volume_mounts {
        name = "tmp"
        path = "/tmp"
      }

      env {
        name  = "END_USER_APP_NAME"
        value = replace(var.endUserAppName, "'", "\\'") # Nginx variables are located inside single quotes
      }

      env {
        name  = "END_USER_APP_ICON"
        value = var.endUserAppIcon
      }

      env {
        name  = "API_HOST"
        value = "https://conversation-api.${azurerm_container_app_environment.this.default_domain}"
      }

      env {
        name  = "OIDC_AUDIENCE"
        value = azuread_application.this.application_id
      }

      env {
        name  = "AZURE_APP_INSIGHTS_CONNECTION_STR"
        value = azurerm_application_insights.this.connection_string
      }
    }

    volume {
      name         = "tmp"
      storage_type = "EmptyDir"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    password_secret_name = "ghcr"
    server               = "ghcr.io"
    username             = var.ghcrUsername
  }

  secret {
    name  = "ghcr"
    value = var.ghcrToken
  }

  tags = local.tags
}

resource "azurerm_container_app" "conversation_api" {
  container_app_environment_id = azurerm_container_app_environment.this.id
  name                         = "conversation-api"
  resource_group_name          = azurerm_resource_group.this.name

  revision_mode = "Single"

  template {
    container {
      cpu    = 1
      image  = "ghcr.io/clemlesne/private-gpt:conversation-api-${var.appVersion}"
      memory = "2Gi"
      name   = "conversation-api"

      liveness_probe {
        failure_count_threshold = 6
        initial_delay           = 15
        interval_seconds        = 5
        path                    = "/health/liveness"
        port                    = 8080
        timeout                 = 5
        transport               = "HTTP"
      }

      # TODO: Create a GitHub issue to add "initial_delay"
      # readiness_probe {
      #   failure_count_threshold = 6
      #   interval_seconds = 15
      #   path             = "/health/readiness"
      #   port             = 8080
      #   timeout          = 5
      #   transport        = "HTTP"
      # }

      startup_probe {
        failure_count_threshold = 10
        interval_seconds        = 5
        port                    = 8080
        transport               = "TCP"
      }

      volume_mounts {
        name = "tmp"
        path = "/tmp"
      }

      env {
        name  = "TMPDIR"
        value = "/tmp"
      }

      env {
        name = "CONFIG_JSON"
        value = jsonencode({
          api = {
            root_path = "/"
          }
          oidc = {
            algorithms = [
              "RS256"
            ]
            api_audience = azuread_application.this.application_id
            issuers = [
              "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/v2.0", # Your Azure AD tenant
              "https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47/v2.0",            # Microsoft tenant-owned applications
              "https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0",            # Xbox, Outlook, etc
            ]
            jwks = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
          }
          monitoring = {
            logging = {
              app_level = "DEBUG"
              sys_level = "DEBUG"
            }
            azure_app_insights = {
              connection_str = azurerm_application_insights.this.connection_string
            }
          }
          persistence = {
            cache = {
              type = "redis"
              config = {
                host     = azurerm_redis_cache.this.hostname
                password = azurerm_redis_cache.this.primary_access_key
                port     = 6380
                ssl      = true
              }
            }
            search = {
              type = "qdrant"
              config = {
                host        = "qdrant.internal.${azurerm_container_app_environment.this.default_domain}"
                https       = true
                port        = 443
                prefer_grpc = false
              }
            }
            store = {
              type = "cosmos"
              config = {
                url      = azurerm_cosmosdb_account.this.endpoint
                database = azurerm_cosmosdb_sql_database.this.name
              }
            }
            stream = {
              type = "redis"
              config = {
                host     = azurerm_redis_cache.this.hostname
                password = azurerm_redis_cache.this.primary_access_key
                port     = 6380
                ssl      = true
              }
            }
          }
          ai = {
            openai = {
              ada_deployment       = azurerm_cognitive_deployment.openai_ada.name
              ada_max_input_tokens = var.openaiAdaModelMaxInputTokens
              ada_model            = var.openaiAdaModelName
              endpoint             = azurerm_cognitive_account.openai.endpoint
              gpt_deployment       = azurerm_cognitive_deployment.openai_gpt.name
              gpt_max_input_tokens = var.openaiGptModelMaxInputTokens
              gpt_model            = var.openaiGptModelName
            }
            azure_content_safety = {
              api_base      = azurerm_cognitive_account.content_safety.endpoint
              api_token     = azurerm_cognitive_account.content_safety.primary_access_key
              max_input_str = 1000
            }
          }
          tools = {
            azure_form_recognizer = {
              api_base  = azurerm_cognitive_account.form_recognizer.endpoint
              api_token = azurerm_cognitive_account.form_recognizer.primary_access_key
            }
            bing = {
              search_url       = "${jsondecode(data.azapi_resource.bing.output).properties.endpoint}/v7.0/search"
              subscription_key = jsondecode(data.azapi_resource_action.bing.output).key1
            }
            tmdb = {
              bearer_token = var.tmdbBearerToken
            }
            news = {
              api_key = var.newsApiKey
            }
            listen_notes = {
              api_key = var.listenNotesApiKey
            }
            open_weather_map = {
              api_key = var.openWeatherMapApiKey
            }
            google_places = {
              api_key = var.googlePlacesApiKey
            }
            azure_cognitive_search = [
              for service in var.azureCognitiveSearch : {
                api_key                = service.api_key
                displayed_name         = service.displayed_name
                index_name             = service.index_name
                language               = service.language
                semantic_configuration = service.semantic_configuration
                service_name           = service.service_name
                top_k                  = service.top_k
                usage                  = service.usage
              }
            ]
            openapi = [
              for service in var.openApi : {
                api_token       = service.api_token
                displayed_name  = service.displayed_name
                schema_yaml_url = service.schema_yaml_url
                usage           = service.usage
              }
            ]
          }
        })
      }
    }

    volume {
      name         = "tmp"
      storage_type = "EmptyDir"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    password_secret_name = "ghcr"
    server               = "ghcr.io"
    username             = var.ghcrUsername
  }

  secret {
    name  = "ghcr"
    value = var.ghcrToken
  }

  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}

resource "azurerm_storage_account" "this" {
  location            = azurerm_resource_group.this.location
  name                = lower(replace(var.resourcePrefix, "-", ""))
  resource_group_name = azurerm_resource_group.this.name

  account_replication_type = "ZRS"
  account_tier             = "Standard"

  tags = local.tags
}

resource "azurerm_storage_share" "qdrant" {
  name                 = "qdrant"
  storage_account_name = azurerm_storage_account.this.name

  quota = 10
}

resource "azurerm_container_app_environment_storage" "qdrant" {
  account_name                 = azurerm_storage_account.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  name                         = azurerm_storage_share.qdrant.name
  share_name                   = azurerm_storage_share.qdrant.name

  access_key  = azurerm_storage_account.this.primary_access_key
  access_mode = "ReadWrite"
}

# Based on the Helm chart, without init container
# See: https://github.com/qdrant/qdrant-helm/blob/main/charts/qdrant/values.yaml
resource "azurerm_container_app" "qdrant" {
  container_app_environment_id = azurerm_container_app_environment.this.id
  name                         = "qdrant"
  resource_group_name          = azurerm_resource_group.this.name

  revision_mode = "Single"

  template {
    max_replicas = 1 # Scaling not enabling because P2P ports and init container are not configured

    container {
      cpu    = 0.25
      image  = "docker.io/qdrant/qdrant:v1.6.1"
      memory = "0.5Gi"
      name   = "qdrant"

      volume_mounts {
        name = "storage"
        path = "/qdrant/storage"
      }

      liveness_probe {
        failure_count_threshold = 6
        initial_delay           = 5
        interval_seconds        = 5
        path                    = "/livez"
        port                    = 6333
        timeout                 = 1
        transport               = "HTTP"
      }

      readiness_probe {
        failure_count_threshold = 6
        interval_seconds        = 5
        path                    = "/readyz"
        port                    = 6333
        timeout                 = 1
        transport               = "HTTP"
      }

      startup_probe {
        failure_count_threshold = 10
        interval_seconds        = 5
        path                    = "/readyz"
        port                    = 6333
        timeout                 = 1
        transport               = "HTTP"
      }
    }

    volume {
      name         = "storage"
      storage_name = azurerm_container_app_environment_storage.qdrant.share_name
      storage_type = "AzureFile"
    }
  }

  # Only using HTTP transport because Container Apps doesn't support multiple ports exposition yet
  ingress {
    external_enabled = false
    target_port      = 6333

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  tags = local.tags
}

