"""HTTP server for Prometheus metrics."""
import time
import os
import logging
from prometheus_client import start_http_server
from src.observability.metrics import *  # This initializes the registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_metrics_server():
    """Start the Prometheus metrics server."""
    # Use standard port 8000 for FastAPI, so use 8001 for pipeline metrics
    port = int(os.environ.get("METRICS_PORT", 8001))
    
    logger.info(f"Starting DCIM Pipeline Metrics server on port {port}")
    try:
        start_http_server(port)
        logger.info(f"Metrics server running. Ready for Prometheus scraper (10.70.0.25:9090)")
        
        # Keep main thread alive
        while True:
            time.sleep(3600)
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")

if __name__ == "__main__":
    run_metrics_server()
