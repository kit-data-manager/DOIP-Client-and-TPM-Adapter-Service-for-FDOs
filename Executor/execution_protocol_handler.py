import re
from Executor.Web_API_executor import Web_API_Executor 
from Executor.script_executor import Script_Executor
class Execution_Protocol_Handler:

    @staticmethod
    def get_ep(execution_map, pits):
        staging_functions = [
        (re.compile(r'script_ep'), Script_Executor.stage_ep), 
        (re.compile(r'21.T11148/a1fe3f60497302ae8b04'), Web_API_Executor.stage_ep),
        (re.compile(r'compandarcheppit'), Web_API_Executor.stage_ep)           
    ]
        for key, value in execution_map.items():
            for pattern, func in staging_functions:
                if pattern.search(key):
                    result=func(execution_map[pattern.pattern], pits)
                    return result