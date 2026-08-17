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
import tempfile

# def run_command(command, capture_output=False):
#     result = subprocess.run(['C:\\Program Files\\Git\\bin\\bash.exe', '-c', command], shell=True, check=True, capture_output=capture_output, text=True)
#     return result.stdout.strip() if capture_output else None

def run_command(command, capture_output=False):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=capture_output, text=True)
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e.cmd}")
        print(f"🔴 Return code: {e.returncode}")
        print(f"📝 Output: {e.output}")
        print(f"⚠️ Error: {e.stderr}")
        raise

# not used in this file, called from target_hydration last line
def patch_app_revision(app_name, NAMESPACE):
    patch = {
        "spec": {
            "destination": {
                "namespace": NAMESPACE,
            }
        }
    }
    patch_str = yaml.dump(patch)
    with tempfile.NamedTemporaryFile('w+', delete=False) as tmpfile:
        tmpfile.write(patch_str)
        tmpfile.flush()
        # run_command(f"kubectl get applications -n argocd",True)
        subprocess.run([
            "kubectl", "patch", "application", app_name,
            "--type=merge", "-n", NAMESPACE,
            "--patch-file", tmpfile.name
        ], check=True)

def caller(REPO_RAW_URL, BB_USERNAME , BB_APP_PASSWORD):

    print("BB_APP_PASSWORD:----------------", BB_APP_PASSWORD)
    print("BB_USERNAME:----------------", BB_USERNAME)
    CRED = base64.b64encode(f"{BB_USERNAME}:{BB_APP_PASSWORD}".encode()).decode()
    app_url = f"{REPO_RAW_URL}"
    print("APP URL:----------------", app_url)
    print("CRED:----------------", CRED)
    headers = {"Authorization": f"Basic {CRED}"}
    response = requests.get(app_url, headers=headers, verify=False)
    # print("RESPONSE:----------------", response.text)
    if response.status_code == 200:
        root_appln_data = yaml.safe_load(response.text)
        print("-------",root_appln_data["spec"]["destination"]["namespace"])
        # root_appln_data["spec"]["destination"]["namespace"] = "argocd"
        # print("-------",root_appln_data["spec"]["destination"]["namespace"])
        ROOT_MAIN_APPLN_TARGET_REVISION = root_appln_data["spec"]["source"]["targetRevision"]
        NAMESPACE = root_appln_data["metadata"]["namespace"]
        # root_main_appln_name = root_appln_data["metadata"]["name"]
        # patch_app_revision(root_main_appln_name)
        with open("application.yaml", "w") as f:
            yaml.dump(root_appln_data, f)
        # run_command("kubectl apply -f application.yaml")
        # print("----------------------------------->  application.yaml successfully applied.")
    else:
        print(f"----------------------------------->  Failed to download application.yaml: HTTP {response.status_code}")

    print ("----------------------------------->  EXIT , CURRENT CONTEXT: ", run_command("kubectl config current-context",True))


    return ROOT_MAIN_APPLN_TARGET_REVISION, NAMESPACE

if __name__ == "__main__":

    BB_USERNAME = os.getenv("BB_USERNAME")
    BB_APP_PASSWORD = os.getenv("BB_APP_PASSWORD")
    REPO_RAW_URL = sys.argv[1]

    ROOT_MAIN_APPLN_TARGET_REVISION, NAMESPACE = caller(REPO_RAW_URL, BB_USERNAME, BB_APP_PASSWORD)
    print("ROOT_MAIN_APPLN_TARGET_REVISION:", ROOT_MAIN_APPLN_TARGET_REVISION)
    print("NAMESPACE:", NAMESPACE)




