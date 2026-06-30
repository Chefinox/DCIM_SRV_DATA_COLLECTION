import logging
import json
import sys
from datetime import datetime, timezone
import traceback

class DCIMJsonFormatter(logging.Formatter):
    """Custom formatter to output JSON logs for the DCIM pipeline."""
    def __init__(self, service_name="dcim-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_entry = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "service": {"name": self.service_name},
            "log": {"level": record.levelname},
            "message": record.getMessage(),
        }
        
        # Mapping for standard fields that might be passed in `extra` dict
        # e.g., logger.info("message", extra={"event_type": "sync_success", "device_type": "server"})
        standard_fields = ["event_type", "device_type", "hostname", "serial_number", "category", "severity"]
        for field in standard_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)
                
        # Add exception traceback if available
        if record.exc_info:
            log_entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
            
        return json.dumps(log_entry)

def setup_logger(service_name, log_file=None, level=logging.INFO):
    """
    Configure and return a standard logger for a DCIM service.
    
    Args:
        service_name (str): Name of the service (e.g., 'dcim-normalizer')
        log_file (str, optional): Path to log file. If None, logs only to stdout.
        level (int, optional): Logging level. Defaults to logging.INFO.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    
    # Clear existing handlers to prevent duplicates if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
        
    formatter = DCIMJsonFormatter(service_name)
    
    # Always log to stdout (helpful for journalctl / systemd)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # If a log file is specified, also log to file
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to console if file is unwritable
            console_handler.setLevel(logging.WARNING)
            logger.warning(f"Failed to setup file handler for {log_file}: {e}", 
                          extra={"event_type": "logger_setup_failure", "category": "OPERATIONAL", "severity": "P3"})
            
    return logger
