from src.a2a_server.config.settings import settings

AGENT_CARD = {
  "name": settings.APP_NAME,
  "description": "Inventory agent handles inventory management and optimization tasks, providing real-time insights and recommendations to ensure efficient stock levels and reduce costs.",
  "url": f"{settings.URL_AGENT}/a2a/message",
  "version": settings.VERSION,
  "provider": {
    "organization": "eliezer-junior",
    "url": f"{settings.URL_AGENT}"
  },
  "supportedInterfaces": [
    {
      "url": f"{settings.URL_AGENT}/a2a/message",
      "protocolBinding": "JSONRPC",
      "protocolVersion": "1.0"
    }
  ],
  "capabilities": {
    "streaming": False,
    "pushNotifications": False,
    "stateTransitionHistory": False,
    "extendedAgentCard": False,
  },
     "securitySchemes": {
    "oauth2": {
      "type": "oauth2",
      "flows": {
        "clientCredentials": {
          "tokenUrl": "https://go-authorization.com/v1/auth",
          "scopes": {
            "a2a:message:send": "Send messages to the agent",
            "a2a:task:read": "Read task status",
            "statistics:compute": "Execute statistical calculations"
          }
        }
      }
    }
  },
  "security": [
    {
      "oauth2": [
        "a2a:message:send"
      ]
    }
  ],
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    {
      "id": "inventory.agent.status",
      "name": "Inventory Agent Status",
      "description": "Returns health status, version, capabilities and runtime information about this inventory agent.",
      "tags": ["health", "information", "status", "diagnostics", "metadata"],
      "additionalProperties": False,
      "inputSchema": {
        "title": "InventoryStatusRequest",
        "type": "object",
          "properties": {}
        },
        "examples": [
          "Show inventory agent status.",
          "Get inventory agent version.",
          "Provide the information and health of the inventory agent.",
          "Give me the diagnostics and metadata of the inventory agent.",
        ],
        "outputModes": ["application/json"],
        "inputModes": ["application/json"]
    },
    {
      "id": "inventory.monitor.observe",
      "name": "Inventory Monitor Observe",
      "description": "Observes inventory state and provides all information related to it.",
      "tags": ["inventory","product","observation"],
      "additionalProperties": False,
      "inputSchema": {
        "type": "object",
        "title": "InventoryMonitorObserveRequest",
        "properties": {
          "product": {
            "type": "object",
            "description":"A product inventory state for observation.",
            "properties": {
              "sku": {
                "type": "string",
                "description": "Unique sku identifier of the product."
              }
            },
            "required": ["sku"]
          }
        },
        "required": ["product"]
      },
      "examples": [
        "Observe inventory state changes for sku-70.",
        "Get insights on inventory changes for product sku-70.",
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    },
    {
      "id": "inventory.monitor.state",
      "name": "Inventory Monitor State",
      "description": "Provides the current state of the inventory for a product.",
      "tags": ["inventory","product","state"],
      "additionalProperties": False,
      "inputSchema": {
        "type": "object",
        "title": "InventoryMonitorStateRequest",
        "properties": {
          "product": {
            "type": "object",
            "description":"A product inventory state for observation.",
            "properties": {
              "sku": {
                "type": "string",
                "description": "Unique sku identifier of the product."
              }
            },
            "required": ["sku"]
          }
        },
        "required": ["product"]
      },
      "examples": [
        "Get the current inventory state for sku-70.",
        "Retrieve inventory details for product sku-70.",
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    },
    {
      "id": "inventory.monitor.reasoning",
      "name": "Inventory Monitor Reasoning",
      "description": "Provides reasoning and insights based on the inventory state for a product.",
      "tags": ["inventory","product","reasoning"],
      "additionalProperties": False,
      "inputSchema": {
        "type": "object",
        "title": "InventoryMonitorReasoningRequest",
        "properties": {
          "product": {
            "type": "object",
            "description":"A product inventory state for observation.",
            "properties": {
              "sku": {
                "type": "string",
                "description": "Unique sku identifier of the product."
              }
            },
            "required": ["sku"]
          }
        },
        "required": ["product"]
      },
      "examples": [
        "Provide reasoning for the inventory state of sku-70.",
        "Get insights on inventory changes for product sku-70.",
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    },
    {
      "id": "inventory.monitor",
      "name": "Inventory Monitor",
      "description": "Monitors inventory state for take actions and provides decision support.",
      "tags": ["inventory","monitoring","decision"],
      "additionalProperties": False,
      "inputSchema": {
        "type": "object",
        "title": "InventoryMonitorRequest",
        "properties": {
          "product": {
            "type": "object",
            "description":"A product inventory state for monitoring.",
            "properties": {
              "sku": {
                "type": "string",
                "description": "Unique sku identifier of the product."
              }
            },
            "required": ["sku"]
          }
        },
        "required": ["product"]
      },
      "examples": [
        "Monitor inventory state changes for product sku-70.",
        "Get insights on inventory monitoring for sku-70.",
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    }
  ]
}