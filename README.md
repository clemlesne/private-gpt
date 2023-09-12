# Employee communication with Private GPT – AI-powered chatbot you can trust

> 👋🏻 Demo available at [private-gpt.shopping-cart-devops-demo.lesne.pro](https://private-gpt.shopping-cart-devops-demo.lesne.pro).

<!-- Use absolute path for images in README.md, so that they are displayed on ArtifactHub.io, Lens, OpenLens, etc. -->
<img src="https://raw.githubusercontent.com/clemlesne/private-gpt/main/logo-512.png" width="100">

Private GPT is a local version of Chat GPT, using Azure OpenAI. It is an enterprise grade platform to deploy a ChatGPT-like interface for your employees.

Includes:

- Can be configured to use any Azure OpenAI completion API, including GPT-4
- Dark theme for better readability
- Dead simple interface
- Deployable on any Kubernetes cluster, with its Helm chart
- Every persistence layers (search, index, AI) is cached, for performance and low cost
- Manage users effortlessly with OpenID Connect
- Monitoring with Azure App Insights (logs, traces, user behaviors)
- More than 150 tones and personalities (accountant, advisor, debater, excel sheet, instructor, logistician, etc.) to better help employees in their specific daily tasks
- Plug and play storage system, including [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/), [Redis](https://github.com/redis/redis) and [Qdrant](https://github.com/qdrant/qdrant).
- Possibility to send temporary messages, for confidentiality
- Salable system based on stateless APIs, cache, progressive web app and events
- Search engine for conversations, based on semantic similarity and AI embeddings
- Unlimited conversation history and number of users
- Usage tracking, for better understanding of your employees' usage

![Application screenshot](docs/ui-conversation.png)

## How it works

### High level

```mermaid
sequenceDiagram
    autonumber

    actor User
    participant PWA
    participant API
    participant OpenAI

    PWA ->> API: Ask for conversations
    activate API
    API ->> API: Get conversations from storage
    API ->> PWA: Answer with conversations
    deactivate API
    User ->> PWA: Select a conversation
    User ->> PWA: Insert a message
    PWA ->> API: Send the message
    activate API
    API ->> OpenAI: Ask for a completion
    activate OpenAI
    OpenAI ->> API: Send completion
    deactivate OpenAI
    API ->> API: Save conversation and message
    API ->> PWA: Answer with the message
    deactivate API
    User ->> PWA: See results
```

### Architecture

```mermaid
graph
    user(["User"])

    api["Conversation service\n(REST API)"]
    ui["Conversation UI\n(PWA)"]

    subgraph tools["Tools"]
        subgraph "Business data"
            cognitive_services["Cognitive services"]
            form_recognizer["Form recognizer"]
            mssql["SQL Server"]
            storage_blob["Blob storage"]
        end

        subgraph "Public data"
            bing["Bing"]
            google_maps["Google Maps"]
            listen_notes["Listen notes"]
            news["News"]
            tmdb["TMDB"]
        end
    end

    subgraph "Persistence"
        cosmosdb[("Cosmos DB\n(disk)")]
        qdrant[("Qdrant\n(disk)")]
        redis[("Redis\n(memory)")]
    end

    subgraph "Azure OpenAI services"
        oai_ada["ADA embedding"]
        oai_gpt["GPT completions"]
        safety["Content Safety"]
    end

    api -- Cache low-level AI results --> redis
    api -- Generate completions --> oai_gpt
    api -- Generate embeddings --> oai_ada
    api -- Index messages --> qdrant
    api -- Orchestrate external capabilities --> tools
    api -- Persist conversations --> cosmosdb
    api -- Test moderation --> safety
    cognitive_services -- Index data --> mssql
    cognitive_services -- Index data --> storage_blob
    ui -- Use APIs --> api
    user -- Use UI --> ui
```

## How to use

### Run locally

Create a local configuration file, a file named `config.toml` at the root of the project. The TOML file can be placed anywhere in the folder or in any parent directory.

```toml
# config.toml
# /!\ All the file values are for example, you must change them
[api]
# root_path = "[api-path]"

[oidc]
algorithms = ["RS256"]
api_audience = "[aad_app_id]"
issuers = ["https://login.microsoftonline.com/[tenant_id]/v2.0"]
jwks = "https://login.microsoftonline.com/common/discovery/v2.0/keys"

[monitoring]

[monitoring.logging]
app_level = "DEBUG" # Enum: "NOSET", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"
sys_level = "WARN" # Enum: "NOSET", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"

[monitoring.azure_app_insights]
connection_str = "InstrumentationKey=[key];[...]"

[persistence]
cache = "redis" # Enum: "redis"
search = "qdrant" # Enum: "qdrant"
store = "cosmos" # Enum: "cache", "cosmos"
stream = "redis" # Enum: "redis"

[persistence.qdrant]
host = "[host]"

[persistence.redis]
db = 0
host = "[host]"

[persistence.cosmos]
# Containers "conversation" (/user_id), "message" (/conversation_id), "user" (/dummy), "usage" (/user_id) must exist
url = "https://[deployment].documents.azure.com:443"
database = "[db_name]"

[ai]

[ai.openai]
ada_deploy_id = "ada"
ada_max_tokens = 2049
api_base = "https://[deployment].openai.azure.com"
gpt_deploy_id = "gpt"
gpt_max_tokens = 4096

[ai.azure_content_safety]
api_base = "https://[deployment].cognitiveservices.azure.com"
api_token = "[api_token]"
max_length = 1000

[tools]

[tools.azure_form_recognizer]
api_base = "https://[deployment].cognitiveservices.azure.com"
api_token = "[api_token]"

[tools.bing]
search_url = "https://api.bing.microsoft.com/v7.0/search"
subscription_key = "[api_token]"

[tools.tmdb]
bearer_token = "[jwt_token]"

[tools.news]
api_key = "[api_token]"

[tools.listen_notes]
api_key = "[api_token]"

[tools.open_weather_map]
api_key = "[api_token]"

[tools.google_places]
api_key = "[api_token]"

[[tools.azure_cognitive_search]]
api_key = "[api_token]"
content_key = "content"
displayed_name = "My search engine"
index_name = "[index_name]"
language = "en-US"
semantic_configuration = "default"
service_name = "[service_name]"
top_k = 10
usage = "Useful when you need legal content contained in one of the codes (incl. civil, commercial, labor, electoral) derived from French legislation. Use this in priority for legal content in France."
```

Now, you can either run the application as container or with live reload. For development, it is recommended to use live reload. For demo, it is recommended to use the container.

With live reload:

```bash
# In each "src/[...]" directory, example "src/conversation-api"
make install start
```

As container:

```bash
make build start logs
```

Then, go to [http://127.0.0.1:8081](http://127.0.0.1:8081).

### Deploy locally

WIP

### Deploy in production

Deployment is container based. Use Helm to install the latest released chart:

```bash
helm repo add clemlesne-private-gpt https://clemlesne.github.io/private-gpt
helm repo update
helm upgrade --install default clemlesne-private-gpt/private-gpt
```

### Get API docs

Go to [http://127.0.0.1:8081/redoc](http://127.0.0.1:8081/redoc).

![Documentation endpoint](docs/api.png)

## [Security](./SECURITY.md)

## Support

This project is open source and maintained by people like you. If you need help or found a bug, please feel free to open an issue on the [clemlesne/private-gpt](https://github.com/clemlesne/private-gpt) GitHub project.

## [Code of conduct](./CODE_OF_CONDUCT.md)

## [Authors](./AUTHORS.md)
