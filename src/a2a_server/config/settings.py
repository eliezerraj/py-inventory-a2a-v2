import os

class Settings:
    def __init__(self):
        self.VERSION = os.getenv("VERSION")
        self.ACCOUNT = os.getenv("ACCOUNT")
        self.APP_NAME = os.getenv("APP_NAME")
        self.HOST = os.getenv("HOST")
        self.PORT = os.getenv("PORT")
        
        self.LIMIT = int(os.getenv("LIMIT"))
        self.SCALE_CHOICE = os.getenv("SCALE_CHOICE")
        self.ANCHOR_CHOICE = os.getenv("ANCHOR_CHOICE")
        
        self.MCP_SERVER_INVENTORY_URL = os.getenv("MCP_SERVER_INVENTORY_URL")
        self.MCP_SERVER_ORDER_URL = os.getenv("MCP_SERVER_ORDER_URL")
        self.A2A_SERVER_STATISTIC_A2A_URL = os.getenv("A2A_SERVER_STATISTIC_A2A_URL")
                
        self.URL_AGENT = os.getenv("URL_AGENT")
        self.SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT"))
   
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        self.OTEL_STDOUT_LOG_GROUP = os.getenv("OTEL_STDOUT_LOG_GROUP", "false").lower() == "true"
        self.LOG_GROUP = os.getenv("LOG_GROUP")

settings = Settings()