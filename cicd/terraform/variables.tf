variable "resourcePrefix" {
  description = "Resources prefix"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-zA-Z0-9-]{2,}$", var.resourcePrefix))
    error_message = "Resource prefix must be at least 3 characters long and start with a lowercase letter"
  }
}

variable "endUserAppName" {
  default = "Private GPT"
  type    = string
}

variable "endUserAppIcon" {
  default = "🔒"
  type    = string
}

variable "appVersion" {
  default = "main"
  type    = string
}

variable "location" {
  type = string
}

variable "selfAccess" {
  default = false
  type    = bool
}

variable "openaiLocation" {
  default  = null
  nullable = true
  type     = string
}

variable "openaiGptModelName" {
  default = "gpt-4-32k"
  type    = string
}

variable "openaiGptModelVersion" {
  default = "0613"
  type    = string
}

variable "openaiGptModelMaxInputTokens" {
  type    = number
  default = 32768
}

variable "openaiAdaModelName" {
  default = "text-embedding-ada-002"
  type    = string
}

variable "openaiAdaModelVersion" {
  default = "2"
  type    = string
}

variable "openaiAdaModelMaxInputTokens" {
  type    = number
  default = 8191
}

variable "tmdbBearerToken" {
  sensitive = true
  type      = string
}

variable "newsApiKey" {
  sensitive = true
  type      = string
}

variable "listenNotesApiKey" {
  sensitive = true
  type      = string
}

variable "openWeatherMapApiKey" {
  sensitive = true
  type      = string
}

variable "googlePlacesApiKey" {
  sensitive = true
  type      = string
}

variable "azureCognitiveSearch" {
  sensitive = true
  type = set(object({
    api_key                = string
    displayed_name         = string
    index_name             = string
    language               = string
    semantic_configuration = string
    service_name           = string
    top_k                  = number
    usage                  = string
  }))
}

variable "openApi" {
  sensitive = true
  type = set(object({
    api_token       = string
    displayed_name  = string
    schema_yaml_url = string
    usage           = string
  }))
}

variable "ghcrUsername" {
  type = string
}

variable "ghcrToken" {
  sensitive = true
  type      = string
}
