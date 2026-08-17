
import subprocess
import os
import sys
import yaml
import time
import socket
import uuid
import json
import urllib3
import tempfile
import requests
import base64
from urllib.parse import urlparse
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_command(command, capture_output=False):
    try:
        result = subprocess.run( command, shell=True, check=True, capture_output=capture_output, text=True )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e.cmd}")
        print(f"🔴 Return code: {e.returncode}")
        print(f"📝 Output: {e.output}")
        print(f"⚠️ Error: {e.stderr}")
        raise

def run_command_bash(command, capture_output=False):
    result = subprocess.run(['C:\\Program Files\\Git\\bin\\bash.exe', '-c', command], shell=True, check=True, capture_output=capture_output, text=True)
    return result.stdout.strip() if capture_output else None

def ensure_namespace(namespace: str):
    try:
        # Check if namespace exists
        subprocess.run(
            ["kubectl", "get", "ns", namespace],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Namespace '{namespace}' already exists. Skipping creation.")
    except subprocess.CalledProcessError:
        # If it doesn't exist, create it
        print(f"Namespace '{namespace}' not found. Creating it...")
        subprocess.run(
            ["kubectl", "create", "ns", namespace],
            check=True
        )

def get_k8s_secret_value(namespace):
    result = subprocess.run(
        ["kubectl", "-n", namespace, "get", "secret", "argocd-initial-admin-secret", "-o", "jsonpath='{.data.password}'"],
        capture_output=True, text=True, check=True
    )
    return base64.b64decode(result.stdout).decode()

def ensure_argo_cd_installed(namespace):
    try:
        # Check if Argo CD is already installed (look for argocd-server deployment)
        check_cmd = ["kubectl", "get", "deploy", "argocd-server", "-n", namespace]
        subprocess.run(check_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ Argo CD is already installed in namespace '{namespace}'")
    except subprocess.CalledProcessError:
        print(f"⬇️ Argo CD not found in '{namespace}', installing...")

        # Download manifest and apply it directly
        url = "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
        response = requests.get(url, verify=False)
        response.raise_for_status()

        apply_cmd = ["kubectl", "apply", "-n", namespace, "-f", "-"]
        subprocess.run(apply_cmd, input=response.text, text=True, check=True)

        print(f"✅ Argo CD successfully installed in namespace '{namespace}'")

def create_server_and_bearer_token(port,NAMESPACE):
    print("inside create server")
    # forwarding port of host clsuter
    ensure_namespace(NAMESPACE)
    ensure_argo_cd_installed(NAMESPACE)
    subprocess.Popen(f"kubectl port-forward svc/argocd-server {port}:443 -n {NAMESPACE}", shell=True)
    # Wait for port  to become available
    for i in range(60):
        try:
            with socket.create_connection(("localhost", port), timeout=2):
                print(f"----------------------------------->  Port-forward established to localhost:{port}")
                break
        except OSError:
            print("----------------------------------->  Waiting for port-forward to be ready...")
            subprocess.Popen(f"kubectl port-forward svc/argocd-server {port}:443 -n {NAMESPACE}", shell=True)
            time.sleep(2)
    else:
        print(f"##########  Failed to connect to localhost:{port}")
        sys.exit(1)
    # HOST_ARGO_PSWD = run_command_bash(
    #     f"kubectl -n {NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath={{.data.password}} | base64 --decode",
    #     capture_output=True
    # )
    HOST_ARGO_PSWD = get_k8s_secret_value(namespace=NAMESPACE)
    # Log in to argocd
    #  --grpc-web is fix if issue remove it !!!!!!!!!!!!!!!!!!!!
    run_command(f"argocd login localhost:{port} --username admin --password {HOST_ARGO_PSWD} --insecure --grpc-web")

    # 1. for swagger ui, checking account.admin has api key or not
    cmd = ["kubectl", "get", "configmap", "argocd-cm", "-n", NAMESPACE , "-o", "yaml"]
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
        cmd = ["kubectl", "patch", "configmap", "argocd-cm", "-n", NAMESPACE, "--type", "merge", "-p", patch_yaml]
        result = subprocess.run(cmd, capture_output=True, check=True)
        print("-----------------------------------> PATA NHI  ")
        print(result.stdout)
        print("----------------------------------->  'accounts.admin: apiKey' added to argocd-cm.")
        subprocess.run(f"kubectl rollout restart deployment argocd-server -n {NAMESPACE}", shell=True, check=True)
    else:
        print("#############  'accounts.admin: apiKey' is already present in argocd-cm.")

    # 4. Generating Bearer token to get repo list and to communicate to API
    result=subprocess.run(f"argocd account generate-token --server localhost:{port}  --insecure", shell=True, check=True, capture_output=True, text=True)
    token = result.stdout.strip()
    if port == 8081:
        print("----------------------------------->  BEARER TOKEN OF HOST CLUSTER : "+token)
    else:
        print("----------------------------------->  BEARER TOKEN OF VCLUSTER : "+token)
    return token, HOST_ARGO_PSWD