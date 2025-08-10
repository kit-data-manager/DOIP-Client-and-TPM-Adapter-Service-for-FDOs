# Reference Implementation for an FDO Service Architecture using DOIP
## Abbreviations:
- KIP: Kernel Information Profile
- TPM: Typed PID Maker
- PID: Persistent Identifier
- FDO: FAIR Digital Object
- DOIP: Digital Object Interface Protocol
- DTR: Data Type Registry

## To reproduce the results, carry out the following steps (you will need to have Docker installed and running):
- clone this repository
- navigate to the local folder and start the docker compose stack using ```docker compose build```
- after building, start the containers using ```docker compose up```
- when the containers are running and the spring build is finished, run the test_tpm.ipynb cells to sequentially print out the results
## FDO records
We duplicated and extended the FDO records of the PIDs available at https://zenodo.org/records/7022736. The original JSON records are stored under [test_data_records](test_data_records). The records were only registered locally using sandbox PIDs, whilst the original ones can be resolved at https://hdl.handle.net/ using the PIDs in the referenced JSON files. The records were created using additional Kernel Information Profiles (KIPs) and Attribute Types that are registered at the ePIC testing DTR (https://dtr-test.pidconsortium.net/), namely:
- KIPs:
    - Helmholtz KIP: https://dtr-test.pidconsortium.net/#objects/21.T11148/b9b76f887845e32d29f7 (for data records)    
    - Operation KIP(inherits from RDA KIP): https://dtr-test.pidconsortium.net/#objects/21.T11148/ea4e93d06a10e15d9cdf (for operation records)

The profiles and typed attributes they contain can be validated by the TPM instance, configured with the ePIC DTR by default.

## The software package comprises three main modules:
- [TPM_Adapter()](flask_app/tpm_adapter.py): provides a client interface by exposing an endpoint .../doip that implements the Digital Object Interface Protocol for HTTP clients. Typically uses the interface of the Typed PID Maker (TPM) Service avialable at https://github.com/kit-data-manager/pit-service.
Implements service specific operations for FDOs, namely:
    - LIST_OPS(): lists all FDO Operations and service operations using the TPM interface
    - LIST_FDOS(): lists all FDOs using the TPM interface
    - GET_FDO(): retrieves the information record associated with the Persistent Identifier of a FDO using the TPM interface
    - GET_RELATED_FDOs(): lists all FDO-FDO relationships for a particular FDO
    - FDO_Operation*(): performs the operation described by a FDO Operation for an associated target FDO using the Mapping_service and Executor
- [Mapping_Service()](flask_app/fdo_fdops_mapping.py): recieves the execution protocol of an FDO Operation record and the targeted FDO record. Transfers the parameters in the execution protocol and the values in the targeted information record into requests and adds them to the excution map. Values for parameter keys are either provided in the FDO Operation record directly (for standard values), are referenced via an attribute key in the target record from where they are mapped, or are passed by the client using the PID of the parameter key and are then directly inserted. The module also considers recursive patterns when sub-operations are described.
  
- [Executor()](flask_app/execute_request.py): Recieves the execution map containing the requests to execute the described operation(s) (currently only requests for Web APIs and Scripts (mainly Python) are supported). Returns the resuls to the TPM_Adapter which sends it to the client.
