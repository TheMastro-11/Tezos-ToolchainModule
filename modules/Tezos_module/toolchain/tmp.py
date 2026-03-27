from pytezos import pytezos
from pprint import pprint # Using pprint for a cleaner dictionary print
from pytezos.contract.entrypoint import ContractEntrypoint

CONTRACT_ADDRESS = "KT1LeAVyPJvwQ9wvHAT9sgh2EJ8oYiuNHGC1"
GHOSTNET_RPC_URL = "https://rpc.ghostnet.teztnets.com/"

try:
    client = pytezos.using(shell=GHOSTNET_RPC_URL)
    contract = client.contract(CONTRACT_ADDRESS) #client.contract(CONTRACT_ADDRESS)
    
    print(f"🔍 Introspecting contract at address: {contract.address}\n")

    print("--- Dynamically Discovering Entrypoints ---")
    
    entrypoints = contract.entrypoints
    #del entrypoints["default"]
    print(entrypoints)
    
    for entrypoint_name, entrypoint_object in contract.entrypoints.items():
        print(f"📌 Entrypoint: \"{entrypoint_name}\"")
        
        try:
            if hasattr(entrypoint_object, 'json_type'):
                parameter_schema = entrypoint_object.json_type()
                
                if parameter_schema.get('title') == 'unit':
                    print("   Parameter: No required (type 'Unit').")
                else:
                    print("   Parameter:")
                    properties = parameter_schema.get('properties', {})
                    for param_name, param_details in properties.items():
                        param_type = param_details.get('title')
                        param_format = f" (details: {param_details.get('format', 'N/D')})"
                        print(f"     - name: `{param_name}`, Type: `{param_type}`{param_format}")
            else:
                param_type = entrypoint_object.prim
                print("   Parameter required:")
                print(f"     - Name: `_` (parametro singolo), Type: `{param_type}`")

        except Exception as e:
            print(f"   ❌ Error Analysing parameter: {e}")
    


except Exception as e:
    print(f"An error occurred: {e}")
