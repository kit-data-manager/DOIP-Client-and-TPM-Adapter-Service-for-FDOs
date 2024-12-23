from flask import Flask, request, jsonify, abort, send_file
import json
import requests
from fdo_fdops_mapping import OperationMapping
from execute_request import Executor
import re
import base64
from setup_db import Neo4j_FDO_Manager
from elasticsearch import Elasticsearch
import logging

app = Flask(__name__)

# Example configuration setting
app.config['MODE'] = 'testing'  # Change to 'deployment' for deployment mode
manager = Neo4j_FDO_Manager()
es = Elasticsearch("http://elasticsearch:9200")
index_name = "fdo_records"
mapping = {
    "mappings": {
        "dynamic": "true"  # Dynamically map fields
    }
}
# Create th ES index
if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body=mapping)
    print(f"Index '{index_name}' created with dynamic mapping!")
else:
    print(f"Index '{index_name}' already exists.")
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
    
def search_fdos(data_query):
    """
    Uses elastic search to retrieve a set of information records based on their contents.
    """
    url = 'http://tpmapp:8090/api/v1/search'
    headers = {
        'accept': 'application/hal+json'
    }
    data=data_query
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        elastic_response = response.json()
        if elastic_response["hits"]["total"] > 0:
            return elastic_response
        else:
            elastic_response = {'error': 'Failed to retrieve records with elastic search.'}
    else:
        elastic_response = {'error': 'Failed to retrieve records with elastic search.'}
        
    return elastic_response

def get_required_input_type(requiredInput):
    key_value_list=[]
    for required_input_type in requiredInput:
        key_value_subsets={}
        required_input_type = convert_value_to_dict(required_input_type['value'])
        for key,value in zip(required_input_type['21.T11148/a976172668c68034d96c'], required_input_type['21.T11148/dece113486d8c5ebcf8d']):
            key_value_subsets[key['value']] = value['value']
        key_value_list.append(key_value_subsets)
    return key_value_list

def check_ops_associations(record):
    if record["entries"]['21.T11148/2694e4a7a5a00d44e62b']:
        # Assumin the record in a operation representing FDO
        key_value_list=get_required_input_type(record["entries"]['21.T11148/2694e4a7a5a00d44e62b'])
        matched_records=execute_elastic_query(key_value_list)
        # Extract documents into a list
        matched_records = [hit["_source"] for hit in matched_records["hits"]["hits"]]
        make_graph_connections(record["pid"], matched_records)
    else:
        # Assuming the record is a non-operation representing FDO
        ops_search_query = {
            "query": {
                "exists": {
                    "field": "21.T11148/2694e4a7a5a00d44e62b"
                }
            }
        }
        operation_records = es.search(index="fdo_records", body=ops_search_query)
        for ops_rec in operation_records:
            if ops_rec["entries"]['21.T11148/2694e4a7a5a00d44e62b']:
                key_value_list=get_required_input_type(ops_rec["entries"]['21.T11148/2694e4a7a5a00d44e62b'])
                matched_records=execute_elastic_query(key_value_list)
                make_graph_connections(record["pid"], matched_records)
                

def make_graph_connections(ops_pid, target_fdo_list):
    # Create connections in the graph db
    manager.add_fdo(ops_pid)
    for ma_rec in target_fdo_list:
        manager.add_fdo(ma_rec["pid"])
        manager.create_fdo_has_operation_relationship(ops_pid, ma_rec["pid"])
    return

def execute_elastic_query(key_value_list):
    query = {
        "query": {
            "bool": {
                "should": [
                    {
                        "bool": {
                            "filter": [
                                {"term": {f"entries.{key}": value}} if value != "NoType" else {"exists": {"field": f"entries.{key}"}}
                                for key, value in subset.items()
                            ]
                        }
                    }
                    for subset in key_value_list
                ]
            }
        }
    }
    response = es.search(index="fdo_records", body=query)
    return response

def create_fdo(record):
    url = 'http://tpmapp:8090/api/v1/pit/pid/?dryrun=false'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    logging.warning(type(record))
    response = requests.post(url, json=record, headers=headers)
    if (response.status_code == 200) or (response.status_code == 201):
        created_record = response.json()
        es.index(index="fdo_records", document=created_record)
        # Check operation associations and ingest in graph db
        check_ops_associations(created_record)
        message = response.text
    else:
        message = {'error': f'FDO record could not be created due to {response.text}.'}

    return message

def get_fdo(target_id):
    """
    Retrieves a specific FDO information record by target_id.
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
    
    # Retrieve FDO Operations associated with a target FDO using the graph database entries
    all_supported_fdops = manager.fetch_associated_nodes(
    start_node_label=target_id,
    relationship="HAS_OPERATION",
)
    return all_supported_fdops

def get_operation_execution_protocol(operation_record):
    supportedProtocols = ['21.T11148/a1fe3f60497302ae8b04']
    for protocol in supportedProtocols:
        if protocol in operation_record["entries"]:
            return convert_value_to_dict(operation_record["entries"][protocol][0]["value"])
    return None

def map_records(operation_id, target_id, client_input=None):
    operation_record = get_fdo(operation_id)
    target_record = get_fdo(target_id)
    mapping = OperationMapping()
    access_protocol = get_operation_execution_protocol(operation_record)
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

    # Call the function to create a new FDO
    elif operation_id.upper() == "0.DOIP/OP.CREATE_FDO" and target_id.upper() == "SERVICE":
        fdo_record=create_fdo(attributes)
        elapsed_time =0
        #print(f"Elapsed time: {elapsed_time:.2f} seconds")
        return({"response": {"created FDO record": fdo_record}, "elapsed_time": elapsed_time})

    # Call the function to list all available functions
    elif operation_id.upper() == "0.DOIP/OP.LIST_OPS" and target_id.upper() == "SERVICE":
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