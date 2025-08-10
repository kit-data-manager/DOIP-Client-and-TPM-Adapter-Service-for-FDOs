import requests
import time
import yaml
import subprocess
import logging
import os
from Executor.execution_protocol_handler import Execution_Protocol_Handler

class Orchestrator:

    def __init__(self, execution_map, config_file='executor_config.yaml'):

        self.execution_map = execution_map
        # Initialize a session for connection reuse
        self.stored_responses = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(base_dir, config_file)
        with open(config_file_path, 'r') as f:
            config = yaml.safe_load(f)

        self.pits = config.get('pids', {})
        self.elapsed_time = 0
        # Function to execute the request with flexibility

    def start_execution(self, is_sub_ep=False):
        result=Execution_Protocol_Handler.get_ep(self.execution_map, self.pits, is_sub_ep)
        return result
