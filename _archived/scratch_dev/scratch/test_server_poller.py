from sys import path
path.append('/home/infra/dcim_metrics_project/scripts')
from dcim_inventory_poller import poll_server
print(poll_server("10.50.0.5"))
