import logging
import uvicorn
import sys

from src.a2a_server.config.settings import settings
from src.a2a_server.transport.http.app import create_app

from prometheus_client import start_http_server

logger = logging.getLogger(__name__)

app = create_app()

def run():
    try:
        logger.info(f"Starting METRICS SERVER: {settings.METRICS_HOST}:{settings.METRICS_PORT}")
        start_http_server(port=int(settings.METRICS_PORT), 
                        addr=settings.METRICS_HOST
        )
        
        logger.info(f"Starting SERVER: {settings.HOST}:{settings.PORT}")
        uvicorn.run(app, 
                    host=settings.HOST, 
                    port=int(settings.PORT),
                    log_level=settings.LOG_LEVEL.lower(),
                )
        
    except Exception as e:
        logger.error(f"Server encountered an error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server stopped SUCCESSFULLY.")
        
# Run the server if this script is executed directly
if __name__ == "__main__":
    run()