import os
import sys
import subprocess
import base64
import requests
import yaml
import time
import socket
import uuid
import json
import urllib3
import kill_port
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# be in vcluster
def get_manifests(ARGOCD_SERVER, app_name, HEADERS, VERIFY_SSL):
    url = f"{ARGOCD_SERVER}/api/v1/applications/{app_name}/manifests"
    # url = f"{ARGOCD_SERVER}/api/v1/applications/{app_name}"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    # print("RESPONSE:----------------", response.text)
    if response.status_code == 404:
        print(f"----------------------------------->  Application '{app_name}' not found.")
        return None
    elif response.status_code != 200:
        print(f"----------------------------------->  Failed to fetch manifests for app '{app_name}': {response.status_code}")
        return None
    response.raise_for_status()
    return response.json()

def get_appln_manifest(ARGOCD_SERVER, app_name, HEADERS, VERIFY_SSL):
    # url = f"{ARGOCD_SERVER}/api/v1/applications/{app_name}/manifests"
    url = f"{ARGOCD_SERVER}/api/v1/applications/{app_name}"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    # print("RESPONSE:----------------", response.text)
    if response.status_code == 404:
        print(f"----------------------------------->  Application '{app_name}' not found.")
        return None
    elif response.status_code != 200:
        print(f"----------------------------------->  Failed to fetch manifests for app '{app_name}': {response.status_code}")
        return None
    response.raise_for_status()
    return response.json()

def run_command(command, capture_output=False):
    result = subprocess.run(['C:\\Program Files\\Git\\bin\\bash.exe', '-c', command], shell=True, check=True, capture_output=capture_output, text=True)
    return result.stdout.strip() if capture_output else None

def create_server_and_bearer_token(port):
    # forwarding port of host clsuter
    subprocess.Popen(f"kubectl port-forward svc/argocd-server {port}:443 -n argocd", shell=True)
    # Wait for port  to become available
    for i in range(10):
        try:
            with socket.create_connection(("localhost", port), timeout=2):
                print(f"----------------------------------->  Port-forward established to localhost:{port}")
                break
        except OSError:
            print("----------------------------------->  Waiting for port-forward to be ready...")
            time.sleep(2)
    else:
        print(f"##########  Failed to connect to localhost:{port}")
        sys.exit(1)
    HOST_ARGO_PSWD = run_command(
        "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode",
        capture_output=True
    )
    # Log in to argocd
    run_command(f"argocd login localhost:{port} --username admin --password {HOST_ARGO_PSWD} --insecure")

    # 1. for swagger ui, checking account.admin has api key or not
    cmd = ["kubectl", "get", "configmap", "argocd-cm", "-n", "argocd", "-o", "yaml"]
    result = subprocess.run(cmd, capture_output=True, check=True)
    configmap_data = yaml.safe_load(result.stdout)

    # 2. Check for the 'accounts.admin: apiKey' entry
    if "data" not in configmap_data or "accounts.admin" not in configmap_data["data"]:
        print(f"############  'accounts.admin: apiKey' not found in argocd-cm. Adding it...")
        # Prepare the patch data
        patch_data = {
            "data": {
                "accounts.admin": "apiKey" #Added login here as well, since the user may want to login.
            }
        }
        # convert patch data to yaml
        patch_yaml = yaml.dump(patch_data)
        
        # 3. Patch the ConfigMap to add the entry
        cmd = ["kubectl", "patch", "configmap", "argocd-cm", "-n", "argocd", "--type", "merge", "-p", patch_yaml]
        result = subprocess.run(cmd, capture_output=True, check=True)
        print("-----------------------------------> CHECK  "+result.stdout)
        print("----------------------------------->  'accounts.admin: apiKey' added to argocd-cm.")
        subprocess.run("kubectl rollout restart deployment argocd-server -n argocd", shell=True, check=True)
    else:
        print("#############  'accounts.admin: apiKey' is already present in argocd-cm.")

    # 4. Generating Bearer token to get repo list and to communicate to API
    result=subprocess.run(f"argocd account generate-token --server localhost:{port}  --insecure", shell=True, check=True, capture_output=True, text=True)
    token = result.stdout.strip()
    if port == 8081:
        print("----------------------------------->  BEARER TOKEN OF HOST CLUSTER : "+token)
    else:
        print("----------------------------------->  BEARER TOKEN OF VCLUSTER : "+token)
    return token

def get_applications(ARGOCD_SERVER, HEADERS, VERIFY_SSL):
    url = f"{ARGOCD_SERVER}/api/v1/applications"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    # print("RESPONSE:", response.text)
    response.raise_for_status()
    return response.json()




def main(file_name_preffix, TOKEN_VCLUSTER,APP_NAME_MATCH):
    print("mainnnn")

    # TOKEN_VCLUSTER=create_server_and_bearer_token(8080)
    ARGOCD_SERVER = "https://localhost:8080"
    VERIFY_SSL = False
    HEADERS = {
        'Authorization': f'Bearer {TOKEN_VCLUSTER}',
        'Accept': 'application/json',
    }

    time.sleep(1)
    # Step 1: Get all applications
    apps_response = get_applications(ARGOCD_SERVER, HEADERS, VERIFY_SSL)
    # print("--------------------------->APPLICATIONS RESPONSE:", apps_response)
    app_items = apps_response.get("items", [])
    # print("--------------------------->APPLICATIONS ITEMS:", app_items)
    APP_NAMES = []
    for i in app_items:
        print("----------------------------------->  APPLICATIONS: ",i.get("metadata", {}).get("name"))
        APP_NAMES.append(i.get("metadata", {}).get("name"))
    # Step 2: For each app, fetch its manifests
    combined_yaml_docs = []
    for app in app_items:
        app_name = app.get("metadata", {}).get("name")
        print(f"----------------------------------->  Application Name: {app_name}")
        if app_name:
            # print(f"Fetching manifests for app: {app_name}")
            # these code should be called when an app_name  exist in app_names parameter
            if app_name in APP_NAME_MATCH:
                manifest_response = get_manifests(ARGOCD_SERVER, app_name, HEADERS, VERIFY_SSL)
                manifests = manifest_response.get("manifests", [])
                for manifest_json in manifests:
                    # print(f">>> Raw JSON: {manifest_json}")
                    try:
                        manifest_dict = json.loads(manifest_json)
                        # print(f">>> Parsed Dict: {manifest_dict}")
                        manifest_yaml = yaml.dump(manifest_dict, sort_keys=False)
                        combined_yaml_docs.append(manifest_yaml.strip())
                    except Exception as e:
                        print(f"Error parsing manifest: {e}")

            # print(f"--------------------------------------------> {manifests}")
            # Step 3: Convert each manifest JSON string -> Python dict -> YAML string
            # for manifest_json in manifests:
            #     manifest_dict = yaml.safe_load(manifest_json)  # convert JSON to dict
            #     manifest_yaml = yaml.dump(manifest_dict, sort_keys=False)  # dict to YAML
            #     combined_yaml_docs.append(manifest_yaml.strip())

            # if isinstance(manifest_response, dict):
            #     try:
            #         manifest_yaml = yaml.dump(manifest_response, sort_keys=False)
            #         combined_yaml_docs.append(manifest_yaml.strip())
            #     except Exception as e:
            #         print(f"Error converting manifest to YAML: {e}")
        
    # Extracting the application manifest
            app_manifest = get_appln_manifest(ARGOCD_SERVER, app_name, HEADERS, VERIFY_SSL)
            if app_manifest:
                # Convert full app manifest dict to YAML string
                manifest_yaml = yaml.dump(app_manifest, sort_keys=False)
                combined_yaml_docs.append(manifest_yaml.strip())                    

    # Step 4: Combine all YAMLs
    final_output = "\n\n---\n\n".join(combined_yaml_docs)
    output_file = f"combined_manifests_{file_name_preffix}.yaml"
    with open(output_file, "w") as f:
        f.write(final_output)
    print(f"\n✅ YAML written to: {output_file}")



if __name__ == "__main__":
    main("target")
    kill_port.main("8080")
