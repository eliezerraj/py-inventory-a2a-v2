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
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    {
      "id": "statistics.agent.status",
      "name": "Statistics Agent Status",
      "description": "Returns health status, version, capabilities and runtime information about this statistics agent.",
      "tags": ["health", "information", "status", "diagnostics", "metadata"],
      "additionalProperties": False,
      "inputSchema": {
        "title": "StatisticsStatusRequest",
        "type": "object",
          "properties": {}
        },
        "examples": [
          "Show statistics agent status.",
          "Get statistics agent version.",
          "Provide the information and health of the statistics agent.",
          "Give me the diagnostics and metadata of the statistics agent.",
        ],
        "outputModes": ["application/json"],
        "inputModes": ["application/json"]
    },
    {
      "id": "inventory.monitor.observe",
      "name": "Inventory Monitor Observe",
      "description": "Observes inventory state changes and provides relevant insights.",
      "tags": ["inventory","monitoring","observation"],
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
      "id": "inventory.monitor",
      "name": "Inventory Monitor",
      "description": "Monitors inventory state and provides relevant insights.",
      "tags": ["inventory","monitoring","observation"],
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