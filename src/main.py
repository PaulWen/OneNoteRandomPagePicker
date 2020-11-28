import json
import sys

import requests

import microsoft_graph_device_flow as auth

config = json.load(open(sys.argv[1]))

accessToken = auth.retrieveAccessToken()

# Calling graph using the access token
graph_data = requests.get(  # Use token to call downstream service
    config["endpoint"],
    headers={'Authorization': 'Bearer ' + accessToken},).json()
print("Graph API call result: %s" % json.dumps(graph_data, indent=2))

