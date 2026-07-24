import routeros_api
import json

IP = "172.16.35.5"
user = "netbox"
pwd = "netbox123"

connection = routeros_api.RouterOsApiPool(IP, username=user, password=pwd, plaintext_login=True)

try:
    api = connection.get_api()
    interfaces = api.get_resource('/interface')
    intf_list = interfaces.get()
    print(f"SUCCESS! Fetched {len(intf_list)} interfaces.")
    print("Interfaces:")
    for intf in intf_list:
        print(f"Name: {intf.get('name')}, Type: {intf.get('type')}, MAC: {intf.get('mac-address')}")
except Exception as e:
    print(f"Error: {e}")
finally:
    connection.disconnect()
