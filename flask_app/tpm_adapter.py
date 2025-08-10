from flask import Flask, request, jsonify, abort, send_file
import json
import requests
import re
import logging
import yaml
import importlib
import importlib.util
import sys
import json
import hashlib
from typing import Optional, List
import sys
from importlib.metadata import version
import ast
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from Executor.orchestrator import Orchestrator
from setup_db import Neo4j_FDO_Manager
from elasticsearch import Elasticsearch

pkg_version = version('elasticsearch')
logging.info(f"elasticsearch version: {pkg_version}")

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
    logging.info(f"Index '{es_index_name}' created with dynamic mapping!")
else:
    logging.info(f"Index '{es_index_name}' already exists.")

# TPM setup
tpm_conf=config.get('tpm', {})
base_url = tpm_conf.get('base_url')
get_known_pids_url = base_url+tpm_conf.get('get_known_pids')
create_fdo_url = base_url+tpm_conf.get('single_pid_url')+"?dryrun=false"
get_fdo_url = base_url+tpm_conf.get('single_pid_url')

# Mapper setup
mapper = config.get('mapper', {})
mapping_protocols = mapper.get('supported_execution_protocols')
module_name=mapper.get('module_name')
file_name = mapper.get('file_name')
class_name = mapper.get('class_name')
spec = importlib.util.spec_from_file_location(module_name, file_name)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load spec for module {module_name} from {file_name}")
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
cls = getattr(module, class_name)
mapper=cls(mapper.get('has_subtypes'), pits)

internal_functions = {
    "0.DOIP/Op.LIST_Ops": {"operationID": "0.DOIP/Op.LIST_Ops", "targetID": "Service or Object", "arguments": "None", "response type": "map of service operation specifications or map of supported FDOPs for the target object"},  # This function lists all available operations
    "0.DOIP/Op.LIST_FDOs": {"operationID": "0.DOIP/Op.LIST_FDOs", "targetID": "Service", "arguments": "None", "response type": "array of FDO PIDs"},
    "0.DOIP/Op.GET_FDO": {"operationID": "0.DOIP/Op.GET_FDO", "targetID": "Object", "arguments": "None", "response type": "PID record"},
    "0.DOIP/Op.GET_RELATED_FDOs": {"operationID": "0.DOIP/Op.GET_RELATED_FDOs", "targetID": "Object", "arguments": "None", "response type": "array of FDO PIDs"},
    "*FDO_Operation": {"operationID": "Object", "targetID": "Object", "arguments": "*", "response type": "JSON object or encoded binary data"}
}

def list_service_ops():
    # List all internal functions available for handle_doip
    return internal_functions

def list_fdos(query_parameters: Optional[List[str]] = None):
    
    if query_parameters is not None:
        fdo_pids=execute_elastic_query(query_parameters, "fdo_records_names")
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

def get_required_input_type(requiredInputTypes):
    key_value_list=[]
    for required_input_type in requiredInputTypes:
        key_value_subsets={}
        required_input_type_dict = convert_value_to_dict(required_input_type['value'])
        to_be_hashed=[]
        for key,value in zip(required_input_type_dict[pits.get('requiredInputKey')], required_input_type_dict[pits.get('requiredInputValue')]):
            if key['value'] in key_value_subsets:
                to_be_hashed.append(key['value'])
                if isinstance(key_value_subsets[key['value']], list):
                    key_value_subsets[key['value']].append(value['value'])
                else:
                    temp=key_value_subsets[key['value']]
                    key_value_subsets[key['value']] = [temp]
                    key_value_subsets[key['value']].append(value['value'])
            else:
                key_value_subsets[key['value']] = value['value']
        if len(to_be_hashed)>0:
            for key in to_be_hashed:
                vals=key_value_subsets[key]
                sorted_items = sorted(vals)
                combined = '|'.join(sorted_items)
                hash_result = hashlib.sha256(combined.encode()).hexdigest()
                key_value_subsets[key] = hash_result
        key_value_list.append(key_value_subsets)
    return key_value_list

def check_ops_associations(record):
    if pits.get('requiredInputType') in record["entries"]:
        # Assumin the record is from an Operation FDO
        key_value_list=get_required_input_type(record["entries"][pits.get('requiredInputType')])
        matched_records=execute_elastic_query(key_value_list, index="fdo_records_pits")
        # Extract documents into a list
        make_operation_graph_connections(record["pid"], matched_records)
    else:
        pass

def make_operation_graph_connections(ops_pid, target_fdo_list):
    # Create new connections in the graph db
    manager.add_fdo_ops(ops_pid)
    
    for ma_rec in target_fdo_list:
        if manager.node_exists("FDO", ma_rec["pid"]):
            pass
        else:
            manager.add_fdo(ma_rec["pid"])
        manager.create_fdo_has_operation_relationship(ma_rec["pid"], ops_pid)
    return

def make_triple_graph_connections(subject_fdo, object_fdo, relation_type):
    # Create new connections in the graph db
    if manager.node_exists("orig_FDO", subject_fdo):
        pass
    else:
        manager.add_orig_fdo(subject_fdo)
    if manager.node_exists("orig_FDO", object_fdo):
        pass
    else:
        manager.add_orig_fdo(object_fdo)
    if relation_type == "hasMetadata":
        if manager.edge_exists(subject_fdo,object_fdo, "HAS_METADATA"):
            return
        else:
            manager.create_fdo_has_metadata_relationship(subject_fdo, object_fdo)
            if manager.node_exists("Service_Operation", "GET_RELATED_FDOs"):
                pass
            else:
                manager.add_service_ops("GET_RELATED_FDOs")
            manager.create_fdo_has_operation_with_service_ops_relationship(subject_fdo, "GET_RELATED_FDOs")
    else:
        if manager.edge_exists(subject_fdo,object_fdo, "IS_METADATA_FOR"):
            return
        else:
            manager.create_fdo_is_metadata_for_relationship(subject_fdo, object_fdo)
            if manager.node_exists("Service_Operation", "GET_RELATED_FDOs"):
                pass
            else:
                manager.add_service_ops("GET_RELATED_FDOs")
            manager.create_fdo_has_operation_with_service_ops_relationship(subject_fdo, "GET_RELATED_FDOs")
    return

def check_record_matches_condition(record: dict, key_value_list: list) -> bool:
    """
    Returns True if the record matches ANY dict in key_value_list (OR across list,
    AND within each dict).
    """
    entries = record.get("entries", {})
    for kv in key_value_list:
        match = True
        for key, value in kv.items():
            if value != "NoType":
                if entries.get(key) != value:
                    match = False
                    break
            else:
                if key not in entries:
                    match = False
                    break
        if match:
            return True
    return False

def execute_elastic_query(key_value_list: list, index: str):
    """
    Returns all docs where ANY dict in the list matches
    (OR across list, AND within each dict).
    """
    should_clauses = []

    for kv in key_value_list:
        must_queries = []
        for key, value in kv.items():
            field = f"entries.{key}"
            if value != "NoType":
                # use the keyword sub‑field for exact matches
                must_queries.append({
                    "term": {f"{field}.keyword": value}
                })
            else:                       # only test that the field exists
                must_queries.append({
                    "exists": {"field": field}
                })
        should_clauses.append({"bool": {"must": must_queries}})

    query = {"query": {"bool": {"should": should_clauses}}}

    resp = es_instance.search(index=index, size=1000, body=query)
    return [hit["_source"] for hit in resp.get("hits", {}).get("hits", [])]

def create_fdo(record):
    url = create_fdo_url
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=record, headers=headers)
    if (response.status_code == 200) or (response.status_code == 201):
        created_record = response.json()
        # Before indexing, convert `created_record` like:
        indexing1 = {"pid": created_record["pid"], "entries": {}}
        indexing2 = {"pid": created_record["pid"], "entries": {}}
        
        for arr in created_record["entries"].values():
            to_be_hashed_names=[]
            to_be_hashed_keys=[]
            for o in arr:
                if o["name"] in indexing1["entries"]:
                    to_be_hashed_names.append(o["name"])
                    to_be_hashed_keys.append(o["key"])
                    if isinstance(indexing1["entries"][o["name"]], list):
                        indexing1["entries"][o["name"]].append(o['value'])
                        indexing2["entries"][o["key"]].append(o['value'])
                    else:
                        temp=indexing1["entries"][o["name"]]
                        indexing1["entries"][o["name"]] = [temp]
                        indexing1["entries"][o["name"]].append(o['value'])
                        temp=indexing2["entries"][o["key"]]
                        indexing2["entries"][o["key"]] = [temp]
                        indexing2["entries"][o["key"]].append(o['value'])
                else:
                    indexing1["entries"][o["name"]] = o["value"]
                    indexing2["entries"][o["key"]] = o["value"]
            if len(to_be_hashed_names)>0:
                for name, key in zip(to_be_hashed_names, to_be_hashed_keys):
                    vals=indexing1["entries"][name]
                    sorted_items = sorted(vals)
                    combined = '|'.join(sorted_items)
                    hash_result = hashlib.sha256(combined.encode()).hexdigest()
                    indexing1["entries"][name] = hash_result
                    indexing2["entries"][key] = hash_result
        es_instance.index(index="fdo_records_names", document=indexing1, refresh="wait_for")
        es_instance.index(index="fdo_records_pits", document=indexing2, refresh="wait_for")

        # Check operation associations and ingest in graph db
        check_ops_associations(created_record)
        # Check pid-triples and ingest in graph db, record for original PIDs, created_record for sandbox PIDs
        check_for_related_fdos(created_record)
        message = response.text
    else:
        message = {'error': f'FDO record could not be created.'}

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

def fetch_neo4j():
    graph_contents = manager.fetch_entire_graph()
    return graph_contents

# Helper function to convert the 'value' string into a dictionary
def convert_value_to_dict(item):
    if isinstance(item, dict):
        return {
            key: convert_value_to_dict(value)
            for key, value in item.items()
        }
    elif isinstance(item, list):
        return [convert_value_to_dict(item) for item in item]
    elif isinstance(item, str):
        try:
            parsed = ast.literal_eval(item)
            if isinstance(parsed, (dict, list)):
                return convert_value_to_dict(parsed)
        except (ValueError, SyntaxError) as e:
            pass
    return item

def list_fdops(target_id):
    
    # Retrieve FDO Operations associated with a target FDO using the graph database entries
    all_supported_fdops = manager.fetch_associated_nodes(
    start_node_label="FDO",
    start_node_property="pid",
    relationship="HAS_OPERATION",
    start_node_value=target_id,
    target_node_label= "Operation_FDO"
)
    all_supported_service_ops1 = manager.fetch_associated_nodes(
    start_node_label="FDO",
    start_node_property="pid",
    relationship="HAS_OPERATION",
    start_node_value=target_id,
    target_node_label= "Service_Operation"
)
    all_supported_service_ops2 = manager.fetch_associated_nodes(
    start_node_label="orig_FDO",
    start_node_property="pid",
    relationship="HAS_OPERATION",
    start_node_value=target_id,
    target_node_label= "Service_Operation"
)
    fdops_list = list(set(node['pid'] for node in all_supported_fdops))
    service_list1 = list(set(node['pid'] for node in all_supported_service_ops1))
    service_list2 = list(set(node['pid'] for node in all_supported_service_ops2))
    return fdops_list+service_list1+service_list2

def get_related_fdos(target_id):

    # Retrieve FDO Operations associated with a target FDO using the graph database entries
    all_related_fdos1 = manager.fetch_associated_nodes(
    start_node_label="orig_FDO",
    start_node_property="pid",
    relationship="HAS_METADATA",
    start_node_value=target_id,
    target_node_label="orig_FDO"
)
    all_related_fdos2 = manager.fetch_associated_nodes(
    start_node_label="orig_FDO",
    start_node_property="pid",
    relationship="IS_METADATA_FOR",
    start_node_value=target_id,
    target_node_label="orig_FDO"
)
    fdos_list = list(set(node['pid'] for node in all_related_fdos1+all_related_fdos2))
    return fdos_list

def get_operation_execution_protocol(operation_fdo_record):
    for protocol in mapping_protocols:
        if protocol in operation_fdo_record["entries"]:
            return convert_value_to_dict(operation_fdo_record["entries"][protocol])
    return None

def map_records(operation_id, target_id, client_input=None):
    operation_fdo_record = get_fdo(operation_id)
    target_fdo_record = get_fdo(target_id)
    execution_protocol = get_operation_execution_protocol(operation_fdo_record)
    if execution_protocol is None:
        return {"error": "Operation execution protocol not supported."}
    # map the operation record's execution protocol with the target_record
    Map=mapper.map_and_transfer(execution_protocol[0], target_fdo_record, client_input)
    execution_map = yaml.safe_load(json.dumps(Map, indent=2))
    return execution_map

def check_for_related_fdos(fdo_record):
    hasMetadataKey = pits.get('hasMetadata')
    isMetadataForKey = pits.get('isMetadataFor')
    if hasMetadataKey in fdo_record["entries"]:
        for i in fdo_record["entries"][hasMetadataKey]:
            make_triple_graph_connections(fdo_record["pid"], i["value"], "hasMetadata")
    if isMetadataForKey in fdo_record["entries"]:
        for i in fdo_record["entries"][isMetadataForKey]:
            make_triple_graph_connections(i["value"], fdo_record["pid"], "isMetadataFor")

def bundle_zip_contents(zip_paths, out_zip_path):
    """Create one ZIP with the contents of each per-job ZIP under its job folder."""
    out_zip_path = Path(out_zip_path)
    out_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out_zip_path, "w", compression=ZIP_DEFLATED) as outz:
        for zp in zip_paths:
            zp = Path(zp)
            job_label = zp.parent.name
            with ZipFile(zp, "r") as src:
                for m in src.infolist():
                    inner = Path(m.filename).as_posix().lstrip("/")
                    outz.writestr(f"{job_label}/{inner}", src.read(m))
    return str(out_zip_path)

@app.route('/doip', methods=['GET', 'POST'])
def handle_doip():
    operation_id = request.args.get('operationId') if request.method == 'GET' else request.json.get('operationId')
    target_id = request.args.get('targetId') if request.method == 'GET' else request.json.get('targetId')

    if request.method == 'POST':
        data = request.get_json()
        attributes = data.get('attributes')
    else:
        attributes=None
    
    # Mandatory parameter check
    if not operation_id or not target_id:
        abort(400, description="Missing mandatory parameter(s).")

    # Call the function to create a new FDO
    elif operation_id.upper() == "0.DOIP/OP.CREATE_FDO" and target_id.upper() == "SERVICE":
        fdo_record=create_fdo(attributes)
        return({"response": {"created FDO record": fdo_record}})

    # Call the function to list all available functions
    elif operation_id.upper() == "0.DOIP/OP.LIST_OPS" and target_id.upper() == "SERVICE":
        available_functions = list_service_ops()
        return jsonify({"response": {"available service operations": available_functions}})
    
    # Call the function to list_FDOs based on specific operationId
    elif operation_id.upper() == "0.DOIP/OP.LIST_FDOS" and target_id.upper() == "SERVICE":
        if attributes:
            fdo_list = list_fdos(attributes)
        else:
            fdo_list = list_fdos()
        return jsonify({"response": {"available FDOs": fdo_list}})
        
    elif operation_id.upper() == "0.DOIP/OP.LIST_OPS" and target_id:
        fdops_list = list_fdops(target_id)
        return jsonify({"response": {"available FDO Operations": fdops_list}})

    elif operation_id.upper() == "0.DOIP/OP.GET_FDO" and target_id:
        fdo_record = get_fdo(target_id)
        return jsonify({"response": {"FDO record": fdo_record}})

    elif operation_id.upper() == "0.DOIP/OP.GET_RELATED_FDOS" and target_id:
        related_fdos=get_related_fdos(target_id)
        
        return jsonify({"response": {"related FDOs": related_fdos}})
    
    elif (operation_id) and (re.match(r'sandboxed\/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', str(target_id))):
        if attributes is not None:
            target_operation_map = map_records(operation_id, target_id, client_input=attributes)
        else:
            target_operation_map = map_records(operation_id, target_id)
        exec = Orchestrator(execution_map=target_operation_map)

        result=exec.start_execution()
        zip_paths = [res["zip_path"] for res in result.values() if res.get("zip_path")]
        if not zip_paths:
            abort(400, "No artifacts were produced.")

        # Make one bundled ZIP
        bundle_root = Path(tempfile.mkdtemp(prefix="bundle_"))
        bundled_zip = bundle_zip_contents(zip_paths, bundle_root / "all_artifacts.zip")

        return send_file(
            bundled_zip,
            mimetype="application/zip",
            as_attachment=True,
            download_name="all_artifacts.zip",
            conditional=True,
            etag=True
        )
    else:
        return jsonify({"error": "Invalid operationId or targetId."})
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)