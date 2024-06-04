from flask import Flask, request, jsonify, abort, send_file
import json
import requests
from fdo_fdops_mapping import OperationMapping
from execute_request import Executor
import re
import time
import base64

app = Flask(__name__)

# Example configuration setting
app.config['MODE'] = 'testing'  # Change to 'deployment' for deployment mode

internal_functions = {
    "0.DOIP/Op.LIST_Ops": {"operationID": "0.DOIP/Op.LIST_Ops", "targetID": "Service or Object", "arguments": "None", "response type": "map of service operation specifications or map of supported FDOPs for the target object"},  # This function lists all available operations
    "0.DOIP/Op.LIST_FDOs": {"operationID": "0.DOIP/Op.LIST_FDOs", "targetID": "Service", "arguments": "None", "response type": "array of FDO PIDs"},
    "0.DOIP/Op.GET_FDO": {"operationID": "0.DOIP/Op.GET_FDO", "targetID": "Object", "arguments": "None", "response type": "PID record"},
    "*FDO_Operation": {"operationID": "Object", "targetID": "Object", "arguments": "*", "response type": "JSON object or encoded binary data"}
}

def list_service_ops():
    # List all internal functions available for handle_doip
    return internal_functions

def list_fdos(fdo_file='fdo_list.json', tpm_arg='fdos'):
    '''if app.config['MODE'] == 'testing':
        # Read from a JSON file in testing mode
        with open(fdo_file, 'r') as file:
            fdo_list = json.load(file)
        return fdo_list
    elif app.config['MODE'] == 'deployment':'''
    # Make a GET request to the external service in deployment mode
    url = 'http://tpmapp:8090/api/v1/pit/known-pid?page=0&size=20'
    headers = {
        'accept': 'application/hal+json'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        fdo_list = response.json()
    else:
        fdo_list = {'error': 'Failed to retrieve data from the external service'}
    return fdo_list
    
def get_fdo(target_id):
    """
    Retrieves the list of all FDOs using the list_fdos function and then searches
    for and returns a specific record by target_id.
    """
    url = f'http://tpmapp:8090/api/v1/pit/pid/{target_id}?validation=false'
    headers = {
        'accept': 'application/json'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        fdo_record = response.json()
    else:
        fdo_record = {'error': f'FDO record with ID {target_id} not found.'}

    return fdo_record

# Function to convert the 'value' string into a dictionary
def convert_value_to_dict(item):
    try:
        # This assumes that the string representation uses single quotes for the outermost layer and does not contain single quotes within strings.
        corrected_json_str = item.replace("'", '"')
        return json.loads(corrected_json_str)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {}

def list_fdops(target_id):
    target_record = get_fdo(target_id)
    fdo_list = list_fdos()
    all_supported_fdops = []
    for fdo in fdo_list:
        supported = True
        fdo_record = get_fdo(fdo['pid'])
        # Check if 'requiredInputType, i.e., 21.T11148/2694e4a7a5a00d44e62b is in the dictionary
        if '21.T11148/2694e4a7a5a00d44e62b' in fdo_record["entries"]:
            # Iterate through each required input type
            for required_input_type in fdo_record["entries"]['21.T11148/2694e4a7a5a00d44e62b']:
                required_input_type = convert_value_to_dict(required_input_type['value'])
                # Check if the required input type is in the reference and matches, or is "NoType"
                if required_input_type['21.T11148/a976172668c68034d96c'][0]['value'] not in target_record['entries']:
                    supported = False
                    break
                if required_input_type['21.T11148/dece113486d8c5ebcf8d'][0]['value'] == 'NoType':
                    pass
                else:
                    if not required_input_type['21.T11148/dece113486d8c5ebcf8d'][0]['value'] == target_record['entries'][required_input_type['21.T11148/a976172668c68034d96c'][0]['value']][0]['value']:
                        break
            if supported:
                # Insert operation PID into the dictionary
                supported_fdops = {}
                supported_fdops["pid"] = fdo['pid']
                # Check if a human-readbable name, i.e., 21.T11148/90ee0a5e9d4f8a668868 is present in the FDO record
                if '21.T11148/90ee0a5e9d4f8a668868' in fdo_record["entries"]:
                    supported_fdops["name"] = fdo_record["entries"]['21.T11148/90ee0a5e9d4f8a668868'][0]['value']
                else:
                    supported_fdops["name"] = "No human-readable name"
                all_supported_fdops.append(supported_fdops)
    return all_supported_fdops

def get_operation_access_protocol(operation_record):
    supportedProtocols = ['21.T11148/a1fe3f60497302ae8b04']
    for protocol in supportedProtocols:
        if protocol in operation_record["entries"]:
            return convert_value_to_dict(operation_record["entries"][protocol][0]["value"])
    return None

def map_records(operation_id, target_id, client_input=None):
    operation_record = get_fdo(operation_id)
    target_record = get_fdo(target_id)
    mapping = OperationMapping()
    access_protocol = get_operation_access_protocol(operation_record)
    if access_protocol is None:
        return {"error": "Operation access protocol not supported."}
    # map the operation record's access protocol with the target_record
    mapping.operation_mapping(access_protocol, target_record, client_input)
    sorted_fdo_fdops_map = {key: mapping.WF[key] for key in sorted(mapping.WF)}
    return sorted_fdo_fdops_map

def execute_request(fdo_fdops_map):
    executor = Executor()
    responses, elapsed_time = executor.select_request(fdo_fdops_map)
    return responses, elapsed_time

@app.route('/doip', methods=['GET', 'POST'])
def handle_doip():
    operation_id = request.args.get('operationId') if request.method == 'GET' else request.json.get('operationId')
    target_id = request.args.get('targetId') if request.method == 'GET' else request.json.get('targetId')

    if request.method == 'POST':
        data = request.get_json()  # Parse JSON data
        # Check if the key exists in JSON, otherwise it's optional
        attributes = data.get('attributes')  # This returns None if 'attributes' does not exist
    else:
        attributes=None
    
    # Mandatory parameter check
    if not operation_id or not target_id:
        abort(400, description="Missing mandatory parameter(s).")

    # Check for specific conditions
    elif operation_id.upper() == "0.DOIP/OP.LIST_OPS" and target_id.upper() == "SERVICE":
        # Call the function to list all available functions
        available_functions = list_service_ops()
        elapsed_time =0
        #print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return jsonify({"response": {"available service operations": available_functions}, "elapsed_time": elapsed_time})

    # Call the function to list_FDOs based on specific operationId
    elif operation_id.upper() == "0.DOIP/OP.LIST_FDOS" and target_id.upper() == "SERVICE":
        fdo_list = list_fdos()
        elapsed_time =0
        #print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return jsonify({"response": {"available FDOs": fdo_list}, "elapsed_time": elapsed_time})
        
    elif operation_id.upper() == "0.DOIP/OP.LIST_OPS" and target_id:
        fdops_list = list_fdops(target_id)
        elapsed_time =0
        #print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return jsonify({"response": {"available FDOps": fdops_list}, "elapsed_time": elapsed_time})

    elif operation_id.upper() == "0.DOIP/OP.GET_FDO" and target_id:
        fdo_record = get_fdo(target_id)
        elapsed_time =0
        #print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return jsonify({"response": {"FDO record": fdo_record}, "elapsed_time": elapsed_time})

    elif (operation_id) and (re.match(r'sandboxed\/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', str(target_id))):
        if attributes is not None:
            fdo_fdops_map = map_records(operation_id, target_id, client_input=attributes)
        else:
            fdo_fdops_map = map_records(operation_id, target_id)
        # Stop timing before the api request function
        #elapsed_time = end_time - start_time
        #print(f"Elapsed time: {elapsed_time:.2f} seconds")
        response, elapsed_time = execute_request(fdo_fdops_map)
        try:
            return jsonify({"response": {"operation result": response}, "elapsed_time": elapsed_time})
        except TypeError as e:
            #print(response)
            # Encoding binary data to Base64 strings
            encoded_response = {key: base64.b64encode(value).decode('utf-8') for key, value in response.items()}

            # Sending the encoded data as JSON
            return jsonify({"response": {"operation result": encoded_response}, "elapsed_time": elapsed_time})
    else:
        return jsonify({"error": "Invalid operationId or targetId."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)