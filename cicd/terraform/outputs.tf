output "conversation_ui_url" {
  value = "https://conversation-ui.${azurerm_container_app_environment.this.default_domain}"
}

output "conversation_api_url" {
  value = "https://conversation-api.${azurerm_container_app_environment.this.default_domain}"
}
