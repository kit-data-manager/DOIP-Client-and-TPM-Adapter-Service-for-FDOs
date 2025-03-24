from flask import Flask, request, jsonify, abort, send_file
import json
import requests
from executor import Executor
import re
import base64
from setup_db import Neo4j_FDO_Manager
from elasticsearch import Elasticsearch
import logging
import yaml
import importlib
import importlib.util
import sys
import json
from typing import Optional, List

app = Flask(__name__)

config_file='tpm_adapter_config.yaml'
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

    # Load PIT configurations
    pits = config.get('pits', {})

# Deployment mode
app.config['MODE'] = config.get('mode', {}) 

# Neo4j setup
neo4j_conf=config.get('graph_db', {})
manager = Neo4j_FDO_Manager(neo4j_conf.get('endpoint'), neo4j_conf.get('name'), neo4j_conf.get('pw'))

# Elastic search setup
ealstic_conf=config.get('elasticsearch', {})
es_instance = Elasticsearch(ealstic_conf.get('endpoint'))
es_index_name = ealstic_conf.get('index_name')
mapping = {
    "mappings": {
        "dynamic": "true"  # Dynamically map fields
    }
}

if not es_instance.indices.exists(index=es_index_name):
    es_instance.indices.create(index=es_index_name, body=mapping)
    print(f"Index '{es_index_name}' created with dynamic mapping!")
else:
    print(f"Index '{es_index_name}' already exists.")

# TPM setup
tpm_conf=config.get('tpm', {})
base_url = tpm_conf.get('base_url')
get_known_pids_url = base_url+tpm_conf.get('get_known_pids')
create_fdo_url = base_url+tpm_conf.get('single_pid_url')+"?dryrun=false"
get_fdo_url = base_url+tpm_conf.get('single_pid_url')

# Mapper setup
mapper = config.get('mapper', {})
mapping_protocols = mapper.get('mapping_protocols')
module_name=mapper.get('module')
file_name = mapper.get('file_name')
class_name = mapper.get('class_name')
spec = importlib.util.spec_from_file_location(module_name, file_name)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load spec for module {module_name} from {file_name}")
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
cls = getattr(module, class_name)
mapper=cls(pits.get('parameterKey'), pits.get('parameterValue'), pits.get('parameterValueType'), mapper.get('has_subtypes'))

internal_functions = {
    "0.DOIP/Op.LIST_Ops": {"operationID": "0.DOIP/Op.LIST_Ops", "targetID": "Service or Object", "arguments": "None", "response type": "map of service operation specifications or map of supported FDOPs for the target object"},  # This function lists all available operations
    "0.DOIP/Op.LIST_FDOs": {"operationID": "0.DOIP/Op.LIST_FDOs", "targetID": "Service", "arguments": "None", "response type": "array of FDO pits"},
    "0.DOIP/Op.GET_FDO": {"operationID": "0.DOIP/Op.GET_FDO", "targetID": "Object", "arguments": "None", "response type": "PID record"},
    "*FDO_Operation": {"operationID": "Object", "targetID": "Object", "arguments": "*", "response type": "JSON object or encoded binary data"}
}

def list_service_ops():
    # List all internal functions available for handle_doip
    return internal_functions

def index_fdo_records():
    url = get_known_pids_url
    headers = {
        'accept': 'application/hal+json'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        fdo_list = response.json()
        for fdo_pid in fdo_list:
            if es_instance.exists(index="fdo_records", id=fdo_pid):
                pass
            else:
                fdo_record=get_fdo(fdo_pid)
                es_instance.index(index="fdo_records", id=fdo_pid, document=fdo_record)
    else:
        fdo_list = {'error': 'Failed to retrieve data from the external service'}
    return

def list_fdos(query_parameters: Optional[List[str]] = None):
    
    if query_parameters is not None:
        fdo_pids=execute_elastic_query(query_parameters)
    else:
        url = get_known_pids_url
        headers = {
            'accept': 'application/hal+json'
        }

        response = requests.get(url, headers=headers)
    if response.status_code == 200:
        fdo_pids = response.json()
    else:
        fdo_pids = {'error': 'Failed to retrieve data from the external service'}
    return fdo_pids

def get_required_input_type(requiredInput):
    key_value_list=[]
    for required_input_type in requiredInput:
        key_value_subsets={}
        required_input_type = convert_value_to_dict(required_input_type['value'])
        for key,value in zip(required_input_type[pits.get('requiredInputKey')], required_input_type[pits.get('requiredInputValue')]):
            key_value_subsets[key['value']] = value['value']
        key_value_list.append(key_value_subsets)
    return key_value_list

def check_ops_associations(record):
    if record["entries"][pits.get('requiredInputType')]:
        # Assumin the record is from an Operation FDO
        key_value_list=get_required_input_type(record["entries"][pits.get('requiredInputType')])
        matched_records=execute_elastic_query(key_value_list)
        # Extract documents into a list
        matched_records = [hit["_source"] for hit in matched_records["hits"]["hits"]]
        make_graph_connections(record["pid"], matched_records)
    else:
        # Assuming the record is from a non-Operation FDO
        ops_search_query = {
            "query": {
                "exists": {
                    "field": pits.get('requiredInputType')
                }
            }
        }
        operation_records = es_instance.search(index="fdo_records", body=ops_search_query)
        for ops_rec in operation_records:
            if ops_rec["entries"][pits.get('requiredInputType')]:
                key_value_list=get_required_input_type(ops_rec["entries"][pits.get('requiredInputType')])
                matched_records=execute_elastic_query(key_value_list)
                make_graph_connections(record["pid"], matched_records)
                

def make_graph_connections(ops_pid, target_fdo_list):
    # Create new connections in the graph db
    manager.add_fdo(ops_pid)
    for ma_rec in target_fdo_list:
        manager.add_fdo(ma_rec["pid"])
        manager.create_fdo_has_operation_relationship(ops_pid, ma_rec["pid"])
    return

def execute_elastic_query(key_value_list: list, subset=False):
    if subset == True:
        
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
        },
        "_source": ["pid"]
    }
    else:
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
    response = es_instance.search(index="fdo_records", body=query)
    return response

def create_fdo(record):
    url = create_fdo_url
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=record, headers=headers)
    if (response.status_code == 200) or (response.status_code == 201):
        created_record = response.json()
        es_instance.index(index="fdo_records", document=created_record)
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
    url = f'{get_fdo_url}{target_id}?validation=false'
    headers = {
        'accept': 'application/json'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        fdo_record = response.json()
    else:
        fdo_record = {'error': f'FDO record with ID {target_id} not found.'}

    return fdo_record

# Helper function to convert the 'value' string into a dictionary
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

def get_operation_execution_protocol(operation_fdo_record):
    for protocol in mapping_protocols:
        if protocol in operation_fdo_record["entries"]:
            return convert_value_to_dict(operation_fdo_record["entries"][protocol][0]["value"])
    return None

def map_records(operation_id, target_id, client_input=None):
    operation_fdo_record = get_fdo(operation_id)
    target_fdo_record = get_fdo(target_id)
    #mapping = OperationMapping()
    execution_protocol = get_operation_execution_protocol(operation_fdo_record)
    if execution_protocol is None:
        return {"error": "Operation execution protocol not supported."}
    # map the operation record's execution protocol with the target_record
    Map=mapper.map_and_transfer(operation_fdo_record, execution_protocol, target_fdo_record, client_input)
    return Map

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
        return jsonify({"response": {"available service operations": available_functions}, "elapsed_time": elapsed_time})

    # Call the function to list_FDOs based on specific operationId
    elif operation_id.upper() == "0.DOIP/OP.LIST_FDOS" and target_id.upper() == "SERVICE":
        fdo_list = list_fdos()
        elapsed_time =0
        return jsonify({"response": {"available FDOs": fdo_list}, "elapsed_time": elapsed_time})
        
    elif operation_id.upper() == "0.DOIP/OP.LIST_OPS" and target_id:
        fdops_list = list_fdops(target_id)
        elapsed_time =0
        return jsonify({"response": {"available FDOps": fdops_list}, "elapsed_time": elapsed_time})

    elif operation_id.upper() == "0.DOIP/OP.GET_FDO" and target_id:
        fdo_record = get_fdo(target_id)
        elapsed_time =0
        return jsonify({"response": {"FDO record": fdo_record}, "elapsed_time": elapsed_time})

    elif (operation_id) and (re.match(r'sandboxed\/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', str(target_id))):
        if attributes is not None:
            target_operation_map = map_records(operation_id, target_id, client_input=attributes)
        else:
            target_operation_map = map_records(operation_id, target_id)
        return jsonify(message="mapped FDO-Ops request", data=target_operation_map)
    else:
        return jsonify({"error": "Invalid operationId or targetId."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)