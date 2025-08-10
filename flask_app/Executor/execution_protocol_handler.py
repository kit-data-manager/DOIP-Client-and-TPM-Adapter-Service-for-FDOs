import re
from .Web_API_executor import Web_API_Executor 
from .script_executor import Script_Executor

class Execution_Protocol_Handler:

    @staticmethod
    def get_ep(execution_map, pits, is_sub_ep):
        staging_functions = [
        (re.compile(r'21.T11148/68a31b6927faf56ea381'), Script_Executor.stage_ep), 
        (re.compile(r'21.T11148/a1fe3f60497302ae8b04'), Web_API_Executor.stage_ep) 
    ]
        for key, value in execution_map.items():
            for pattern, func in staging_functions:
                if pattern.search(key):
                    if is_sub_ep:
                        result=func(execution_map[pattern.pattern], pits, is_sub_ep)
                    else:
                        result=func(execution_map[pattern.pattern], pits)
                    return result