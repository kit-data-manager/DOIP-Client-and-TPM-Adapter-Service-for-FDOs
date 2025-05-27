from Executor.generic_executor import Generic_Executor


class Script_Executor(Generic_Executor):
        
    
    def set_execution_sequence(parameter_type, parameter_array, execution_requests):
        if parameter_array is not None:
            for parameter in parameter_array:
                match (parameter_type, parameter[2]):
                    case ("scriptMethod", x) if "true" in x:
                        execution_requests=Script_Executor.extend_execution_sequence_multiple_request(parameter, execution_requests, " ")
                    case ("scriptMethod", x) if "false" in x:
                        execution_requests=Script_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
                    case ("scriptargument", x) if "true" in x:
                        execution_requests=Script_Executor.extend_execution_sequence_multiple_request(parameter, execution_requests, " ")
                    case ("scriptargument", x) if "false" in x:
                        execution_requests=Script_Executor.extend_execution_sequence_single_request(parameter, execution_requests, " ")
            return execution_requests
        else:
            return execution_requests
        
    
    @staticmethod
    def stage_ep(execution_protocol, pits):
        ''' Script execution protocol staging'''
        installations = Script_Executor.check_parameter(execution_protocol, pits.get('installations'))
        #manage_installation_requirements(installations)
        method = Script_Executor.check_parameter(execution_protocol, pits.get('scriptMethod'))
        arguments = Script_Executor.check_parameter(execution_protocol, pits.get('scriptargument'))

        execution_requests = {}
        execution_requests=Script_Executor.set_execution_sequence('scriptMethod', method, execution_requests)
        execution_requests=Script_Executor.set_execution_sequence('scriptargument', arguments, execution_requests)
        results=Script_Executor.execute_requests(execution_requests)
        #print("3",results)
        #åreturn results
    @staticmethod
    def check_parameter(execution_protocol, parameter):
        if parameter in execution_protocol:
            parameter = execution_protocol.get(parameter)
            return parameter
        else:
            return None

#Testing
'''with open("executor_config.yaml", 'r') as pits_file:
    config = yaml.safe_load(pits_file)
    
pits = config.get('pids', {})

with open("test_executor_curl2.json", 'r') as test:
    test_executor_curl = yaml.safe_load(test)

curl_ep_test=Script_Executor()
curl_ep_test.stage_ep(test_executor_curl, pits)'''