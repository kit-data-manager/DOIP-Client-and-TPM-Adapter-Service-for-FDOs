from fdo_fdops_mapping import OperationMapping
from execute_request import Executor
import json

with open("/Users/nicolasblumenroehr/Downloads/FDO-Ops-Service-Architecture-main/extended_records/publication1.json", 'r') as file:
    # Parse the JSON data and convert it into a Python dictionary
    data_dict = json.load(file)

with open("/Users/nicolasblumenroehr/Downloads/FDO-Ops-Service-Architecture-main/extended_records/recommend_publication.json", 'r') as file:
    # Parse the JSON data and convert it into a Python dictionary
    ops_dict = json.load(file)
corrected_json_str = ops_dict["entries"]["21.T11148/a1fe3f60497302ae8b04"][0]["value"].replace("'", '"')
ops_rec = json.loads(corrected_json_str)
mapper = OperationMapping()
mapp = mapper.operation_mapping(ops_rec, data_dict)
print(mapper.WF)
executor = Executor()
response = executor.select_request(mapper.WF)
print(response)