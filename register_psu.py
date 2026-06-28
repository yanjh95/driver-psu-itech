# pyrefly: ignore [missing-import]
import pyvisa
import json
import os

def register_new_psu(registry_file="psu_registry.json"):
    # Load existing registry
    registry = {}
    if os.path.exists(registry_file):
        with open(registry_file, "r") as f:
            registry = json.load(f)
        print(f"Loaded existing registry with {len(registry)} PSUs from '{registry_file}'")
    else:
        print(f"Registry file '{registry_file}' not found. Initializing a new registry...")
            
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    
    if not resources:
        print("No VISA instruments found plugged into your laptop.")
        return
        
    print(f"Found {len(resources)} connected instruments.")
    
    unregistered = []
    for res in resources:
        if res not in registry:
            unregistered.append(res)
            
    if not unregistered:
        print("All connected instruments are already in the registry!")
        return
        
    for res in unregistered:
        print(f"\nFound UNREGISTERED instrument: {res}")
        add_it = input("Would you like to add this to the registry? (y/n): ")
        if add_it.lower().strip() == 'y':
            model = input("Enter the Model name (e.g. IT6953A): ")
            desc = input("Enter a description: ")
            
            # Use a try block to handle non-integers gracefully
            while True:
                try:
                    maxV = float(input("Enter Max Voltage limit (V): "))
                    maxA = float(input("Enter Max Current limit (A): "))
                    maxP = float(input("Enter Max Power limit (W): "))
                    break
                except ValueError:
                    print("Please enter numeric values!")

            registry[res] = {
                "model": model,
                "description": desc,
                "maxV": maxV,
                "maxA": maxA,
                "maxP": maxP
            }
            print(f"Added {model} to registry queue.")
            
    # Save the updated registry
    with open(registry_file, "w") as f:
        json.dump(registry, f, indent=4)
        
    print(f"\nRegistry updated! Handled {len(registry)} total instruments.")

if __name__ == "__main__":
    register_new_psu()
