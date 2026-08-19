from datetime import datetime
import time
event_time_str = datetime.utcnow().isoformat()
event_time = datetime.fromisoformat(event_time_str).timestamp()
print("event time:", event_time, "current time:", time.time())
