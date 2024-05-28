import requests
import time

class Executor:
    def __init__(self):
        # Initialize a session for connection reuse
        self.stored_responses = {}
        self.pids = {
            "contentHeaderType":  "21.T11148/66c4de21f77739edb009",
            "httpEndpointLocation": "21.T11148/50b78494937d6085d763",
            "httpMethod": "21.T11148/791a2295375e3cd9dfee",
            "httpHeaders": "21.T11148/e92d9f23abd63ebea855",
            "httpQueries": "21.T11148/916ca3badfa68b06870c",
            "httpBody": "21.T11148/0c055f37730ce8b376e5",
            "httpFile": "21.T11148/3591e6f2f123dcc14aee",
            "order": "21.T11148/cce55e4309a753985bdd",
            "httpParameterKey": "21.T11148/574c609fddc9a50c409f",
            "httpParameterValue": "21.T11148/d08567465008206eb123",
            "asArray": "21.T11148/931e01f99fcb1a4f60e7",
            "httpParameterValueMap": "21.T11148/859aae499b8021af1ad9",
            "httpEndpointPathParameter": "21.T11148/23f7a91300c3db80aa9f"
        }
        self.elapsed_time = 0
    # Function to execute the request with flexibility

    def check_argument_reference(self, argument):
        for key, value in argument.items():
            if value in list(self.stored_responses.keys()):
                argument[key] = self.stored_responses[value]
        return argument

    def execute_flexible_request(self, order, request_index, request):
        # Basic request components
        method = request.get(self.pids['httpMethod'], 'GET').lower()  # Default to 'GET' if not specified
        url = request[self.pids['httpEndpointLocation']]

        if self.pids["httpEndpointPathParameter"] in request:
            url = url+request[self.pids["httpEndpointPathParameter"]]
            
        try:
            # Optional components with defaults to None or {}
            headers = request.get(self.pids['httpHeaders'], {})
            params = request.get(self.pids['httpQueries'], {})
            data = request.get(self.pids['httpBody'], {})
            files = request.get(self.pids['httpFile'], {})
            content_type = request.get(self.pids['contentHeaderType'], {})
            if content_type == "application/json":
                json_data = data
                data={}
            else:
                json_data = None
            headers = self.check_argument_reference(headers)
            params = self.check_argument_reference(params)
            data = self.check_argument_reference(data)
            files = self.check_argument_reference(files)

        except KeyError as e:
            print(e)
            pass
        

        # Prepare request arguments excluding None values
        request_kwargs = {
            'headers': headers or None,
            'params': params or None,  # Exclude if empty
            'data': data or None,      # Exclude if empty
            'json': json_data or None,  # Exclude if empt
            'files': files or None,      # Exclude if empty
        }
        # Filter out None values to ensure only provided parameters are passed to requests
        request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}

        start_time = time.perf_counter()

        # Dynamically calling the requests method based on the 'method'
        try:
            response = requests.request(method, url, **request_kwargs)
            end_time = time.perf_counter()
            self.elapsed_time = end_time - start_time
            if response.ok:
                # Here, you can decide what part of the response to store
                # For simplicity, we're storing the raw content, but you could store response.json(), response.text, etc.
                response_key = "request {}.{}".format(order, request_index)
                try:
                    self.stored_responses[response_key] = response.json()
                except Exception as e:
                    self.stored_responses[response_key] = response.content
            else:
                print(f"Request to {url} failed with status code:", response.status_code, request_kwargs)
        except ValueError as e:
            print(f"An error occurred: {e}", request_kwargs)
            return None

    def select_request(self, fdo_fdops_map):
        for order in fdo_fdops_map:
            for request in fdo_fdops_map[order]:
                self.execute_flexible_request(order, request, fdo_fdops_map[order][request])
        return self.stored_responses, self.elapsed_time
