import requests
import time
import yaml
import subprocess
import ast
import platform
import sys
import re
import logging
from Executor.execution_protocol_handler import Execution_Protocol_Handler

class Orchestrator:

    def __init__(self, execution_map, config_file='executor_config.yaml'):

        self.execution_map = execution_map
        # Initialize a session for connection reuse
        self.stored_responses = {}
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        self.pits = config.get('pids', {})
        self.elapsed_time = 0
        # Function to execute the request with flexibility

    def start_execution(self):
        result=Execution_Protocol_Handler.get_ep(self.execution_map, self.pits)
        return result
    
    def check_redundancy(self):
        pass

    def execute_ep(self, execution_array):

        result = subprocess.run(execution_array, capture_output=True, text=True)

        # Check if the command was successful
        if result.returncode == 0:
            print("Response:", result.stdout)
        else:
            print("Error:", result.stderr)
        return result.stdout
