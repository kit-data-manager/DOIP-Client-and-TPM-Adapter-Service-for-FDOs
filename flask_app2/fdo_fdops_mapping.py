import re
from jsonschema import validate
import ast

class OperationMapping:
    def __init__(self, has_subtypes, pits):
        self.parameter_key = pits.get('parameter_key')
        self.parameter_value = pits.get('parameter_value')
        self.has_subtypes = has_subtypes

    def map_and_transfer(self, execution_protocol, target_fdo_record, client_input=None):
        print(execution_protocol)
        execution_protocol_type = execution_protocol.get('key')
        
        Map = {execution_protocol_type: {}}
        try:
            # Evaluate the string as a Python dictionary
            execution_protocol['value'] = ast.literal_eval(execution_protocol['value'])
        except (ValueError, SyntaxError) as e:
            print("Error converting string to dictionary:", e)
        for parameter, parameter_objects in execution_protocol['value'].items():
            parameter_type = parameter
            for parameter_object in parameter_objects:
                parameter_key, parameter_value, merge_repeated_entries = self.set_parameter_elements(parameter_object["value"])
                original_parameter_value = None
                # If the parameter value specifies a sub-execution protocol parameter array,
                # map and transfer it recursively.
                validation = self.is_sub_ep(parameter_value)
                if validation:
                    sub_execution_map = self.map_and_transfer(parameter_value, target_fdo_record)
                    original_parameter_value = parameter_value
                    parameter_value = sub_execution_map
                elif re.search(r"([0-9]+\.T[0-9]+/[a-fA-F0-9]+)", parameter_value):
                    
                    extracted_value = self.extract_value_from_target_record(parameter_value, target_fdo_record)
                    if isinstance(extracted_value, list):
                        extracted_value = str(extracted_value)
                    original_parameter_value = parameter_value
                    parameter_value = extracted_value
                # Check if the parameter value was provided in the payload of the client input.
                if (client_input is not None) and (parameter_type in client_input):
                    parameter_value=self.merge_with_client_input(client_input[parameter_type], parameter_value, original_parameter_value, merge_repeated_entries)
                Map= self.add_to_map(Map, execution_protocol_type, parameter_type, parameter_key, parameter_value, merge_repeated_entries)
        return Map
    
    def merge_with_client_input(self, client_input_value, parameter_value, original_parameter_value, merge_repeated_entries):
        pattern = merge_repeated_entries[1]
        prefix, delimiter, suffix = pattern[0], pattern[1], pattern[2]
        parameter_value=ast.literal_eval(parameter_value)
        constructed_value = ""
        for element in parameter_value:
            constructed_value+=f"{element}{delimiter}"
        if (prefix is not None) and (suffix is not None):
            f"{prefix}{constructed_value}{suffix}"

        merged_parameter_value = re.sub(original_parameter_value, constructed_value, client_input_value)
        return merged_parameter_value

    def deep_search(self, record, pattern):
        matching_value = []
    
        if isinstance(record, dict):
            for key, value in record.items():
                matching_value.extend(self.deep_search(value, pattern))
        
        elif isinstance(record, (list, tuple, set)):
            for item in record:
                matching_value.extend(self.deep_search(item, pattern))
        
        elif isinstance(record, str):
            if re.search(pattern, record):
                matching_value.append(record)
        
        return matching_value
    
    def extract_value_from_target_record(self, parameter_value, target_fdo_record):
        pit = re.search(r"([0-9]+\.T[0-9]+/[a-fA-F0-9]+)", parameter_value)
        if pit.group(1) not in target_fdo_record["entries"]:
            for entry_list in target_fdo_record["entries"]:
                for entry in entry_list:
                    print(entry_list, entry)
                    matching_value = self.deep_search(entry["value"])
            return re.sub("([0-9]+\.T[0-9]+/[a-fA-F0-9]+)", matching_value, parameter_value)
        else:
            matching_value = []
            for entry in target_fdo_record["entries"][pit.group(1)]:
                matching_value.append(re.sub("([0-9]+\.T[0-9]+/[a-fA-F0-9]+)", entry["value"], parameter_value))
        return matching_value
    
    def add_to_map(self, Map, execution_protocol_type, parameter_type, parameter_key, parameter_value, merge_repeated_entries):
        if parameter_type in Map[execution_protocol_type]:
            Map[execution_protocol_type][parameter_type].append((parameter_key, parameter_value, merge_repeated_entries))
        else:
            Map[execution_protocol_type][parameter_type] = [(parameter_key, parameter_value, merge_repeated_entries)]
        return Map

    def set_parameter_elements(self, parameter_object_value):
        if self.has_subtypes is False:
            # Unpack the list into three variables
            parameter_key, parameter_value, merge_repeated_entries = parameter_object_value[0], parameter_object_value[1], parameter_object_value[2]
            return parameter_key, parameter_value, merge_repeated_entries
        else:
            parameter_key = parameter_object_value["value"][self.parameter_key][0]["value"]
            parameter_value = parameter_object_value["value"][self.parameter_value][0]["value"]
        return parameter_key, parameter_value, merge_repeated_entries

    def is_sub_ep(self, parameter_value):
        if isinstance(parameter_value, dict):
            return True
        else:
            return False

#Testing
'''if __name__ == '__main__':
    # Define the file names. Adjust paths if needed.
    execution_protocol_file = '../test_scripts/get_related_terms_ops.json'
    target_fdo_record_file = '../test_scripts/test_target_record.json'
    client_input_file = '../test_scripts/client_input.json'
    pits_yaml_file = 'tpm_adapter_config.yaml'
    
    # Load pits from YAML.
    with open(pits_yaml_file, 'r') as pits_file:
        pits = yaml.safe_load(pits_file)

    # Load the execution protocol JSON.
    with open(execution_protocol_file, 'r') as ep_file:
        execution_protocol = json.load(ep_file)

    # Load the target FDO record JSON.
    with open(target_fdo_record_file, 'r') as tf_file:
        target_fdo_record = json.load(tf_file)

    # Load the client input JSON. This file is optional.
    if os.path.exists(client_input_file):
        with open(client_input_file, 'r') as ci_file:
            client_input = json.load(ci_file)
    else:
        client_input = None
    
# Create an instance of OperationMapping.
op_map = OperationMapping(has_subtypes=False, pits=pits)
with open(execution_protocol_file, 'r') as file:
    ops = json.load(file)
# Call the map_and_transfer function.
result_map = op_map.map_and_transfer(ops["entries"]["21.T11148/a1fe3f60497302ae8b04"][0], target_fdo_record, client_input)

# Print the resulting map.
print("Resulting Map:")
print(json.dumps(result_map, indent=2))'''