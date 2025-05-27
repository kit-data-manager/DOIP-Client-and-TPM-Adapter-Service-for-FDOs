import json
import subprocess
import platform
import logging
import re
from abc import ABC, abstractmethod
import ast

class Generic_Executor(ABC):

    @abstractmethod
    def initiate_sub_execution_protocol(sub_ep):
        from Executor.orchestrator import Orchestrator
        sub_exec = Orchestrator(sub_ep)
        result=sub_exec.start_execution()
        return result

    @abstractmethod
    def set_execution_sequence(parameter_type, parameter_array, execution_requests):
        pass

    def manage_installation_requirements(installations):
        if installations is None:
            return 
        system = platform.system()
        try:
            if system == 'Linux':
                # For Debian/Ubuntu systems:
                cmd=['sudo', 'apt-get', 'install', '-y',]
                cmd.extend(installations)
                subprocess.run(['sudo', 'apt-get', 'update'], check=True)
                subprocess.run(cmd, check=True)
                return
            elif system == 'Darwin':  # macOS
                # Installing Python via Homebrew:
                cmd=['brew', 'install',]
                cmd.extend(installations)
                subprocess.run(cmd, check=True)
                return
            elif system == 'Windows':
                # For Windows, assume Chocolatey is installed:
                cmd=['choco', 'install',]
                cmd.extend(installations)
                subprocess.run(cmd, check=True)
                return
            else:
                logging.error("Unsupported operating system for installation requirements")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error installing: {e}")
    
    def extend_execution_sequence_single_request(parameter, execution_requests, arg_separator=""):
        if isinstance(parameter[1], dict):
            temp_execution_requests = {}
            index=1
            sub_eps=Generic_Executor.initiate_sub_execution_protocol(parameter[1])
            if len(execution_requests)>1:
                for request in execution_requests:
                    for sub_ep in sub_eps.values():
                        temp_execution_requests[index]=execution_requests[request]+parameter[0]+" "+sub_ep+arg_separator
                        index+=1
                    index+=1
            elif len(execution_requests)==1:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=execution_requests[1]+parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            else:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            execution_requests=temp_execution_requests

        elif isinstance(parameter[1], list):
            if len(execution_requests)>1:
                for request in execution_requests:
                    execution_requests[request]+=parameter[0]+" "+arg_separator
                    for value in parameter[1]:
                        execution_requests[request]+=value+","
                    execution_requests[request]+=arg_separator
            else:
                execution_requests[1]+=parameter[0]+" "
                for value in parameter[1]:
                    execution_requests[1]+=value+","
                execution_requests[1]+=arg_separator
        else:
            if len(execution_requests)>1:
                for request in execution_requests:
                    execution_requests[request]+=parameter[0]+" "+parameter[1]+arg_separator
            elif len(execution_requests)==1:
                execution_requests[1]+=parameter[0]+" "+parameter[1]+arg_separator
            else:
                execution_requests[1]=parameter[0]+" "+parameter[1]+arg_separator
        return execution_requests
    
    def extend_execution_sequence_multiple_request(parameter, execution_requests, arg_separator=""):
        if isinstance(parameter[1], dict):
            temp_execution_requests = {}
            index=1
            sub_eps=Generic_Executor.initiate_sub_execution_protocol(parameter[1])
            if len(execution_requests)>1:
                for request in execution_requests:
                    for sub_ep in sub_eps.values():
                        temp_execution_requests[index]=execution_requests[request]+parameter[0]+" "+sub_ep+arg_separator
                        index+=1
                    index+=1
            elif len(execution_requests)==1:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=execution_requests[1]+parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            else:
                for sub_ep in sub_eps.values():
                    temp_execution_requests[index]=parameter[0]+" "+sub_ep+arg_separator
                    index+=1
            execution_requests=temp_execution_requests
        elif isinstance(parameter[1], list):
            temp_execution_requests = {}
            index=1
            if len(execution_requests)>1:
                for request in execution_requests:
                    for value in parameter[1]:
                        temp_execution_requests[index]=execution_requests[request]+parameter[0]+" "+value+arg_separator
                        index+=1
                    index+=1
            elif len(execution_requests)==1:
                for value in parameter[1]:
                    temp_execution_requests[index]=execution_requests[1]+parameter[0]+" "+value+arg_separator
                    index+=1
            else:
                for value in parameter[1]:
                   temp_execution_requests[index]=parameter[0]+" "+value+arg_separator
                index+=1
            execution_requests=temp_execution_requests
        else:
            if len(execution_requests)>1:
                for request in execution_requests:
                    execution_requests[request]+=parameter[0]+" "+parameter[1]+arg_separator
            elif len(execution_requests)==1:
                execution_requests[1]+=parameter[0]+" "+parameter[1]+arg_separator
            else:
                execution_requests[1]=parameter[0]+" "+parameter[1]+arg_separator

        return execution_requests
    
    @staticmethod
    @abstractmethod
    def stage_ep():
        pass

    @staticmethod
    @abstractmethod
    def check_parameter():
        pass

    def execute_requests(execution_requests):
        resolved_results = {}
        for k, v in execution_requests.items():
            if isinstance(v, str):
                print(f"\nProcessing entry {k}...")
                #final_result = Generic_Executor.resolve_sub_executions(v)
                resolved_results[k] = Generic_Executor.execute_command(v)
        for k, result in resolved_results.items():
            print(f"{k}: {result}")


    def replace_sub_execution(text):
    # The regex finds "sub_execution:" followed by a { then any number of non-"}" characters, until the first "}".
    # This assumes that the dictionary does not contain nested } characters.
        return re.sub(r'sub_execution:\{[^}]+\}', '-', text)
    
    def execute_command(command_str):
        """Executes a shell command and returns the result as string."""
        print(f"Executing: {command_str}")
        result = subprocess.run(command_str, shell=True, capture_output=True, text=True)
        print("result", result)
        return result.stdout.strip()