import json
import re
import copy

class OperationMapping:
    def __init__(self):
        self.M_a = {}
        self.M_r = {}
        self.WF = {}
        self.httpParameters=["21.T11148/e92d9f23abd63ebea855", "21.T11148/916ca3badfa68b06870c", "21.T11148/0c055f37730ce8b376e5", "21.T11148/3591e6f2f123dcc14aee", "21.T11148/23f7a91300c3db80aa9f"]
        self.pids = {
            "contentHeaderType":  "21.T11148/66c4de21f77739edb009",
            "httpEndpointLocation": "21.T11148/50b78494937d6085d763",
            "httpMethod": "21.T11148/791a2295375e3cd9dfee",
            "httpHeaders": "21.T11148/e92d9f23abd63ebea855",
            "httpQueries": "21.T11148/916ca3badfa68b06870c",
            "httpBody": "21.T11148/0c055f37730ce8b376e5",
            "httpFile": "21.T11148/3591e6f2f123dcc14aee",
            "order": "21.T11148/cce55e4309a753985bdd",
            "httpParameterKey": "21.T11148/574c609fddc9a50c409f",
            "httpParameterValue": "21.T11148/d08567465008206eb123",
            "asArray": "21.T11148/931e01f99fcb1a4f60e7",
            "httpParameterValueMap": "21.T11148/859aae499b8021af1ad9",
            "httpEndpointPathParameter": "21.T11148/23f7a91300c3db80aa9f"
        }
    def add_request_to_M(self, order, new_request, parameter, value, sub_ops=None, index=None, restrictedUpdate=False):
        
        if order in self.M_r:
            if new_request:
                number_requests = len(self.M_r[order])
                temp_M_r = {}
                for existing_request in self.M_r[order]:
                    new_request_content = copy.deepcopy(self.M_r[order][existing_request])
                    new_request_content.update({parameter: copy.deepcopy(value)})
                    temp_M_r[number_requests+index] = new_request_content
                self.M_r[order].update(temp_M_r)
            else:
                for existing_request in self.M_r[order]:
                    if restrictedUpdate:
                        if self.M_r[order][existing_request][parameter].items() <= value.items():
                            self.M_r[order][existing_request].update({parameter: copy.deepcopy(value)})
                    else:
                        if (parameter in self.M_r[order][existing_request]) and (isinstance(self.M_r[order][existing_request][parameter], str)):
                            self.M_r[order][existing_request][parameter] += f', {value}'
                        else:
                            self.M_r[order][existing_request].update({parameter: copy.deepcopy(value)})
        else:
            if sub_ops is not None:
                self.M_r[order] = {1: sub_ops}
            else:
                self.M_r[order] = {1: {parameter: copy.deepcopy(value)} }
            

    def operation_mapping(self, operation_protocol, data_record, client_input=None):
        # Add all mapped operation parameters to map M_a
        self.operation_order = operation_protocol["21.T11148/cce55e4309a753985bdd"][0]["value"]
        del operation_protocol["21.T11148/cce55e4309a753985bdd"]

        for parameter in operation_protocol:
            M_a = {}
            M_t = {}
            for arg in operation_protocol[parameter]:
                if (parameter in self.httpParameters) and (isinstance(arg["value"], dict)):
                    parameter = parameter
                    arg_key = arg["value"]["21.T11148/574c609fddc9a50c409f"][0]["value"]
                    arg_value = arg["value"]
                    if "21.T11148/859aae499b8021af1ad9" in arg_value:
                        arg_value=arg_value["21.T11148/859aae499b8021af1ad9"]
                        temp={}
                        sub_mapping = OperationMapping()
                        sub_mapping.M_r = self.M_r
                        sub_mapping.operation_mapping(arg_value[0]["value"], data_record)
                        sub_ops_order = sub_mapping.operation_order
                        for index, request_index in enumerate(list(sub_mapping.M_r[sub_ops_order].keys())):
                            M_a[arg_key] = "{}.{}".format(str(sub_ops_order), str(request_index))
                            if len(M_t) > 0:
                                for temp_map in M_t:
                                    M_a_temp = copy.deepcopy(M_a)
                                    M_a_temp.update(M_t[temp_map])
                                    if index == 0:
                                        self.add_request_to_M(self.operation_order, False, parameter, M_a_temp, index=index, restrictedUpdate=True)
                                    else:
                                        M_a_temp.update(M_t[temp_map])
                                        self.add_request_to_M(self.operation_order, True, parameter, M_a_temp, index=index)
                                    next_temp_key = max(temp.keys()) + 1 if temp else 0
                                    temp[next_temp_key] = M_a_temp
                            else:
                                M_a_temp = copy.deepcopy(M_a)
                                if index == 0:
                                    self.add_request_to_M(self.operation_order, False, parameter, M_a_temp, index=index)
                                else:
                                    self.add_request_to_M(self.operation_order, True, parameter, M_a_temp, index=index)
                                next_temp_key = max(temp.keys()) + 1 if temp else 0
                                temp[next_temp_key] = M_a_temp
                        temp_cp = copy.deepcopy(temp)
                        M_t.update(temp_cp)

                    elif "21.T11148/d08567465008206eb123" in arg_value:
                        arg_value=arg_value["21.T11148/d08567465008206eb123"]
                    else:
                        #print("assign from client", client_input, parameter)
                        arg_value["21.T11148/d08567465008206eb123"]=[{"key": "21.T11148/d08567465008206eb123", "name": "httpParameterValue", "value": client_input[parameter]}]
                        arg_value=arg_value["21.T11148/d08567465008206eb123"]

                    if re.match(r'^[0-9]+\.T[0-9]+/[a-fA-F0-9]+$', str(arg_value[0]["value"])):
                        asArray = arg["value"]["21.T11148/931e01f99fcb1a4f60e7"][0]["value"]
                        if asArray == "True":
                            M_a[arg_key] = []
                            for value in data_record["entries"][arg_value[0]["value"]]:
                                value=value["value"]
                                M_a[arg_key].append(value)
                            self.add_request_to_M(self.operation_order, False, parameter, M_a)
                        else:
                            for index, value in enumerate(data_record["entries"][arg_value[0]["value"]]):
                                value=value["value"]
                                M_a[arg_key] = value
                                self.add_request_to_M(self.operation_order, True, parameter, M_a, index=index)
                    else:
                        #asArray = arg["value"]["21.T11148/931e01f99fcb1a4f60e7"][0]["value"]
                        arg_value_list = []
                        for value in arg_value:
                            arg_value_list.append(value["value"])
                        M_a[arg_key] = arg_value_list
                        self.add_request_to_M(self.operation_order,False, parameter, M_a)
                else:
                    parameter_value = arg["value"]
                    if re.match(r'^[0-9]+\.T[0-9]+/[a-fA-F0-9]+$', str(parameter_value)):
                        if len(data_record["entries"][parameter_value]) > 1:
                            for index, value in enumerate(data_record["entries"][parameter_value]):
                                parameter_value_temp=value["value"]
                                self.add_request_to_M(self.operation_order, True, parameter, parameter_value_temp, index=index)
                        else:
                            value=data_record["entries"][parameter_value][0]["value"]
                            self.add_request_to_M(self.operation_order, False, parameter, value)
                    else:
                        self.add_request_to_M(self.operation_order, False, parameter, parameter_value)
        self.WF=self.M_r