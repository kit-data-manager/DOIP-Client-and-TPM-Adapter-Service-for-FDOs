from Executor.generic_executor import Generic_Executor
import json
import subprocess
import tempfile

class Web_API_Executor(Generic_Executor):
    
    def set_execution_sequence(parameter_type, parameter_array, execution_requests):
        if parameter_array is not None:
            for parameter in parameter_array:
                match (parameter_type, parameter[2]):
                    case ("httpMethod", _):
                        execution_requests[1]="curl -L "+parameter[0]+" "+parameter[1]+" "
                    case ("httpHeaders", x) if "array" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpHeaders", _):
                        execution_requests=Web_API_Executor.extend_execution_sequence_multiple_request(parameter, execution_requests, " ")
                    case ("httpQueries", x) if "array" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpQueries", _):
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpBody", x) if "array" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpBody", _):
                        execution_requests=Web_API_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("httpBody", x) if "json" in x:
                        execution_requests=Web_API_Executor.extend_execution_sequence_json_body(parameter, execution_requests, " ")
                        
            return execution_requests
        else:
            return execution_requests

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
    
    '''def extend_curl_command(parameter_type, parameter, execution_array):
        if parameter_type == "httpMethod":
            if isinstance(parameter[1], list):
                execution_array.extend(parameter[1])
            elif isinstance(parameter[1], str):
                execution_array.append(parameter[1])'''
    
    def stage_ep(execution_protocol, pits):
        ''' Curl execution protocol staging'''
        installations = Web_API_Executor.check_parameter(execution_protocol, pits.get('installations'))
        #manage_installation_requirements(installations)
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
        results=Web_API_Executor.execute_requests(execution_requests)
        return results
    
    def execute_requests(execution_requests):
        resolved_results = {}
        for k, v in execution_requests.items():
            if isinstance(v, str):
                print(f"\nProcessing entry {k}...")
                #final_result = Generic_Executor.resolve_sub_executions(v)
                resolved_results[k] = Web_API_Executor.execute_command(v)
        #for k, result in resolved_results.items():
            #print(f"{k}: {result}")
        return resolved_results

    def check_parameter(execution_protocol, parameter):
        if parameter in execution_protocol:
            parameter = execution_protocol.get(parameter)
            return parameter
        else:
            return None
        

    def execute_command(command_str):
        """Executes a shell command and returns the result as string."""
        print(f"Executing: {command_str}")
        result = subprocess.run(command_str, shell=True, capture_output=True, text=True)
        print("!",result.stdout)
        file_content = result.stdout
        # Write content to a temporary file.
        tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", delete=False)
        tmp_file.write(file_content)
        tmp_file.close()
        #print("555",tmp_file.name)
        return tmp_file.name

#testing
'''with open("executor_config.yaml", 'r') as pits_file:
    config = yaml.safe_load(pits_file)
    
pits = config.get('pids', {})

with open("test_executor_curl.json", 'r') as test:
    test_executor_curl = yaml.safe_load(test)

curl_ep_test=Web_API_Executor()
curl_ep_test.stage_ep(test_executor_curl, pits)'''