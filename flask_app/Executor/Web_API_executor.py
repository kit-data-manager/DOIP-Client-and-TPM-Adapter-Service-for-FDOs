from Executor.generic_executor import Generic_Executor
import json
import subprocess
import tempfile
import re
import ast
import logging

class Web_API_Executor(Generic_Executor):
    
    def set_execution_sequence(parameter_type, parameter_array, execution_requests):
        if parameter_array is not None:
            for parameter in parameter_array:
                match (parameter_type, parameter[2]):
                    case ("httpMethod", _):
                        if parameter[0] == "GET":
                            parameter[1]=Web_API_Executor.parse_maybe_list(parameter[1])
                            if isinstance(parameter[1], list):
                                for element in range(0, len(parameter[1])):
                                    tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", delete=False)
                                    execution_requests[element]="curl -L "+" "+parameter[1][element]+" "+"-o"+" "+tmp_file.name+" "
                            else:
                                tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", delete=False)
                                execution_requests[1]="curl -L "+" "+parameter[1]+" "+"-o"+" "+tmp_file.name+" "
                        else:
                            parameter[1]=Web_API_Executor.parse_maybe_list(parameter[1])
                            if isinstance(parameter[1], list):
                                for element in range(0, len(parameter[1])):
                                    execution_requests[element]="curl -L "+" "+parameter[0]+" "+parameter[1][element]+" "
                            else:
                                execution_requests[1]="curl -L "+" "+parameter[0]+" "+parameter[1]+" "
                    case ("httpHeaders", x) if "true" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpHeaders", x) if not x or "false" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_multiple_request(parameter, execution_requests, " ")
                    case ("httpQueries", x) if "true" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpQueries", x) if not x or "false" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpBody", x) if "true" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpBody", x) if not x or "false" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpBody", x) if "true" in x and isinstance(parameter[1], dict):
                        execution_requests=Web_API_Executor.extend_execution_sequence_json_body(parameter, execution_requests, " ")
            return execution_requests
        else:
            return execution_requests
    def parse_maybe_list(s):
        try:
            result = ast.literal_eval(s)
            if isinstance(result, list):
                return result
            else:
                return s  # Not a list, return as-is
        except (ValueError, SyntaxError):
            return s  # Not a valid Python literal
    
    def extend_execution_sequence_json_body(parameter, execution_requests):
        if isinstance(parameter[1], dict):
            result=Web_API_Executor.initiate_sub_execution_protocol(parameter[1])
            parameter[1]=result
        if len(execution_requests)>1:
            for request in execution_requests:
                exists=False
                for index, element in enumerate(request):
                    if parameter[0] in element:
                        object1 = json.loads(request[index+1])
                        object2 = json.loads(parameter[1])
                        merged_objects = {**object1, **object2}
                        merged_json_str = json.dumps(merged_objects)
                        execution_requests[request][index+1]=merged_json_str+"\\"
                        exists=True
                        break
                if exists==False:
                    execution_requests[request]+=parameter[0]+" "+parameter+"\\"
        else:
            exists=False
            for index, element in enumerate(execution_requests[1]):
                if parameter[0] in element:
                    object1 = json.loads(execution_requests[1][index+1])
                    object2 = json.loads(parameter[1])
                    merged_objects = {**object1, **object2}
                    merged_json_str = json.dumps(merged_objects)
                    execution_requests[1][index+1]=merged_json_str+"\\"
                    exists=True
                    break
            if exists==False:
                execution_requests[1]+=parameter[0]+" "+parameter+"\\"
        return execution_requests
    
    def stage_ep(execution_protocol, pits, is_sub_ep=False):
        ''' Curl execution protocol staging'''
        installations = Web_API_Executor.check_parameter(execution_protocol, pits.get('installations'))
        Web_API_Executor.manage_installation_requirements(installations)
        method = Web_API_Executor.check_parameter(execution_protocol, pits.get('httpMethod'))
        header = Web_API_Executor.check_parameter(execution_protocol, pits.get('httpHeaders'))
        query = Web_API_Executor.check_parameter(execution_protocol, pits.get('httpQueries'))
        data = Web_API_Executor.check_parameter(execution_protocol, pits.get('httpBody'))
        file = Web_API_Executor.check_parameter(execution_protocol, pits.get('httpFile'))

        execution_requests = {}
        execution_requests=Web_API_Executor.set_execution_sequence('httpMethod', method, execution_requests)
        execution_requests=Web_API_Executor.set_execution_sequence('httpHeaders', header, execution_requests)
        execution_requests=Web_API_Executor.set_execution_sequence('httpQueries', query, execution_requests)
        execution_requests=Web_API_Executor.set_execution_sequence('httpBody', data, execution_requests)
        execution_requests=Web_API_Executor.set_execution_sequence('httpFile', file, execution_requests)
        if is_sub_ep:
            results=Web_API_Executor.execute_requests_sub_ep(execution_requests)
        else:
            results=Web_API_Executor.execute_requests(execution_requests)
        return results
    
    def execute_requests_sub_ep(execution_requests):
        resolved_results = {}
        for k, v in execution_requests.items():
            if isinstance(v, str):
                logging.info(f"\nProcessing entry {k}...")
                resolved_results[k] = Web_API_Executor.execute_command_sub_ep(v)
        return resolved_results

    def check_parameter(execution_protocol, parameter):
        if parameter in execution_protocol:
            parameter = execution_protocol.get(parameter)
            return parameter
        else:
            return None

    def execute_command_sub_ep(command_str):
        """Executes a shell command and returns the result as string."""
        logging.info(f"Executing: {command_str}")
        if ".tmp" in command_str:
            match = re.search(r'\S+\.tmp', command_str)
            if match:
                logging.info("Found:", match.group())
            else:
                logging.info("No .tmp file found.")
            result = subprocess.run(command_str, shell=True, text=True)
            return match.group()
        else:
            result = subprocess.run(command_str, shell=True, capture_output=True, text=True)
            file_content = result.stdout
            # Write content to a temporary file.
            tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", delete=False)
            tmp_file.write(file_content)
            tmp_file.close()
            return tmp_file.name