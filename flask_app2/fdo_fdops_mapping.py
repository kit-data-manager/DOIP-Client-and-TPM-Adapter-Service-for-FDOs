import json
import re
import copy

class OperationMapping:

    def __init__(self, parameter_key, parameter_value, parameter_value_type, has_subtypes):
        self.parameter_key = parameter_key
        self.parameter_value = parameter_value
        self.parameter_value_type = parameter_value_type
        self.has_subtypes = has_subtypes

    def map_and_transfer(self, execution_protocol, target_fdo_record, client_input=None):

        for parameter_object in execution_protocol:
            Map = {}
            for parameter in parameter_object:
                parameter_key, parameter_value, parameter_value_type = self.set_parameter_elements(parameter)

                #If the parameter value specifies a sub-execution protocol parameter array, map and transfer it recursively.
                if parameter_value_type == "object":
                    sub_operation = OperationMapping()
                    #sub_operation.Map = self.Map
                    sub_execution_map = sub_operation.map_and_transfer(parameter_value, target_fdo_record)
                    Map[parameter_key] = (sub_execution_map, parameter_value_type)
                else:
                    # check if the parameter value was provided in the payload of the client input
                    if parameter_key in client_input:
                        parameter_value = client_input[parameter_key]
                        Map[parameter_key] = (parameter_value, parameter_value_type)
                    else:
                        if re.match(r'^[0-9]+\.T[0-9]+/[a-fA-F0-9]+$', parameter_value):
                            if target_fdo_record["entries"][parameter_value] > 1:
                                parameter_value = []
                                for matching_value in target_fdo_record["entries"][parameter_value]:
                                    parameter_value.append(matching_value)
                            else:
                                parameter_value = target_fdo_record["entries"][parameter_value][0]["value"]
                        else:
                            pass
                        Map[parameter_key] = (parameter_value, parameter_value_type)
        return Map

    def set_parameter_elements(self, parameter_object):
        if self.has_subtypes == False:
            for parameter in parameter_object:
                parameter_key = parameter["value"][0]
                parameter_value = parameter["value"][1]
                parameter_value_type = parameter["value"][2]
        else:
            for parameter in parameter_object:
                parameter_key = parameter["value"][self.parameter_key][0]["value"]
                parameter_value = parameter["value"][self.parameter_value][0]["value"]
                parameter_value_type = parameter["value"][self.parameter_value_type][0]["value"]
        return parameter_key, parameter_value, parameter_value_type