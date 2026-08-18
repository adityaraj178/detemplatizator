# inputs
# extracting list of appln from the vcluster serer and then channging target revision of the application.yaml file
# and then deploying the application.yaml file to the vcluster server

# req: target-branch-name, app_manifests
import in_source
# import in_consolidate_call
import in_consolidate_backup

import subprocess
import base64
import requests
import socket
import os
import sys
import yaml
import time
import socket
import uuid
import json
import urllib3
import tempfile
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

def get_argocd_password():
    result = subprocess.run(
        ["kubectl", "-n", "argocd", "get", "secret", "argocd-initial-admin-secret", "-o", "json"],
        check=True, capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    encoded_password = data["data"]["password"]
    return base64.b64decode(encoded_password).decode("utf-8")

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
    HOST_ARGO_PSWD = run_command_bash(
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
    return token, HOST_ARGO_PSWD

def create_clone_url_from_raw_url(RAW_URL):
    try:
        parsed_url = urlparse(RAW_URL)
        path_segments = parsed_url.path.split('/')
        # Expected format: /users/{user}/repos/{repo}/raw/...
        if len(path_segments) >= 5 and path_segments[1] == 'users' and path_segments[3] == 'repos':
            user = path_segments[2]
            repo = path_segments[4]
            bitbucket_base = os.getenv("BITBUCKET_BASE_URL", "")
            clone_url = f"{bitbucket_base}/scm/~{user}/{repo}.git"
            return clone_url
        else:
            return None  # URL doesn't match expected format
    except Exception as e:
        print(f"Error: {e}")
        return None  # Handle any parsing errors

def get_manifests(ARGOCD_SERVER, app_name, HEADERS, VERIFY_SSL):
    url = f"{ARGOCD_SERVER}/api/v1/applications/{app_name}"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    print("response:",response )
    # print("RESPONSE:----------------", response.text)
    if response.status_code == 404:
        print(f"----------------------------------->  Application '{app_name}' not found.")
        return None
    elif response.status_code != 200:
        print(f"----------------------------------->  Failed to fetch manifests for app '{app_name}': {response.status_code}")
        return None
    response.raise_for_status()
    return response.json()

def patch_app_revision_for_root(app_name, new_branch, NAMESPACE):
    patch = {
        "spec": {
            "source": {
                "targetRevision": new_branch
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

# Patch application with new revision
def patch_app_revision(app_name, new_branch, manifest, NAMESPACE):
    spec = manifest.get("spec", {})

    if "source" in spec:
        # Single source case
        # Create patch to change targetRevision
        patch = {
            "spec": {
                "source": {
                    "targetRevision": new_branch
                }
            }
        }
    elif "sources" in spec:
        updated_sources = []
        for source in spec["sources"]:
            # if "helm" not in source and "bitbucket.gob.amadeus.net" in source.get("repoURL", ""):
            if "helm" not in source:
                updated_source = {
                    **source,
                    "targetRevision": new_branch
                }
                updated_sources.append(updated_source)
            else:
                updated_sources.append(source)

        patch = {
            "spec": {
                "sources": updated_sources
            }
        }
    else:
        print("No source or sources found in manifest")

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
        
        # import os
    # os.remove(tmpfile.name)

# Sync application
def refresh_app(app_name):
    subprocess.run([
        "argocd", "app", "sync", app_name,
        "--insecure", "--grpc-web"
    ], check=True)

def disable_app_controller(NAMESPACE):
    run_command(f"kubectl -n {NAMESPACE} scale deployment argocd-applicationset-controller --replicas=0",True)
    print("scaled appst controoler to 0")

def enable_app_controller(NAMESPACE):
    run_command(f"kubectl -n {NAMESPACE} scale deployment argocd-applicationset-controller --replicas=1",True)
    print("scaled appst controoler to 1")

def get_applications(ARGOCD_SERVER, HEADERS, VERIFY_SSL):
    url = f"{ARGOCD_SERVER}/api/v1/applications"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    # print("RESPONSE:", response.text)
    response.raise_for_status()
    return response.json()

def start_port_forward(namespace, local_port=8080, remote_port=443):
    # Use svc/argocd-server or pod/argocd-server depending on your setup
    return subprocess.Popen(
        f"kubectl port-forward svc/argocd-server -n {namespace} {local_port}:{remote_port}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def wait_for_argocd(port=8080, retries=5, delay=2):
    import requests
    for i in range(retries):
        try:
            r = requests.get(f"https://localhost:{port}/healthz", verify=False)
            if r.status_code == 200:
                return True
        except:
            time.sleep(delay)
    return False

def refresh_app_with_retry(app_name, namespace):
    try:
        run_command(f"argocd app get {app_name} --refresh --server localhost:8080 --insecure", True)
        print("  ✅ refreshed")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "error forwarding port" in stderr or "actively refused it" in stderr:
            print("  🔁 Port-forward failed. Attempting to restart...")
            pf_proc = start_port_forward(namespace)
            if wait_for_argocd():
                try:
                    run_command(f"argocd app get {app_name} --refresh --server localhost:8080 --insecure", True)
                    print("  ✅ refreshed after restarting port-forward")
                except subprocess.CalledProcessError as e2:
                    print(f"  ❌ Retry failed: {e2.stderr}")
            else:
                print("  ❌ Argo CD server still unreachable after port-forward retry.")
        else:
            print(f"  ⚠️ refresh failed: {stderr}")


def main( target_branch, target_new, TARGET_REPO_CLONE_URL, RAW_URL, ROOT_MAIN_APPLN_TARGET_REVISION, FILE_SUFFIX, TOKEN_VCLUSTER, VCLUSTER_ARGOCD_PASSWORD,APP_NAME_MATCH,NAMESPACE):
    # TOKEN_VCLUSTER, VCLUSTER_ARGOCD_PASSWORD=create_server_and_bearer_token(8080)
    ARGOCD_SERVER = "https://localhost:8080"
    VERIFY_SSL = False
    HEADERS = {
        'Authorization': f'Bearer {TOKEN_VCLUSTER}',
        'Accept': 'application/json',
    }
    # if (TARGET_REPO_CLONE_URL == RAW_URL):
    #     print("#############  Target repo URL and raw URL are same.")
    
    # login to argocd vscluster
    print("VCLUSTER_ARGOCD_PASSWORD:----------------", VCLUSTER_ARGOCD_PASSWORD)
    run_command(f"argocd login  localhost:8080 --username admin --password {VCLUSTER_ARGOCD_PASSWORD} --insecure --grpc-web ", capture_output=True)
    

    # BELOW ONE line 186 not sure, hit and trial
    patch_app_revision_for_root("myapp-root-application",target_new,NAMESPACE)
    time.sleep(5)

    #  -----------------------TEST--------FOR APP-NAMES-LIST-----------------
    appsTEST_response = get_applications(ARGOCD_SERVER, HEADERS, VERIFY_SSL)
    appTEST_items = appsTEST_response.get("items", [])
    APP_NAMES = []
    for i in appTEST_items:
        print("---------------------test-------------->  APPLICATIONS: ",i.get("metadata", {}).get("name"))
        APP_NAMES.append(i.get("metadata", {}).get("name"))

    # ----------------------TEST-END-------------------------



    
    RAW_CLONE_URL = create_clone_url_from_raw_url(RAW_URL);
    for app_name in APP_NAMES:
        print(f"----------------------------------->  Application Name: {app_name}")

        manifest = get_manifests(ARGOCD_SERVER, app_name, HEADERS, VERIFY_SSL)
        spec = manifest.get("spec", {})
        if "source" in spec:
            # Single source case
            repo_url = spec["source"]["repoURL"]
            print("Single source repo URL:", repo_url)
        elif "sources" in spec:
            # Multi-source case: filter out helm sources
            for source in spec["sources"]:
                if "helm" not in source:
                    repo_url = source.get("repoURL")
                    print("Multi-source (non-helm) repo URL:", repo_url)
        else:
            print("No source or sources found in manifest")

        # print("TARGET_REPO_CLONE_URL:----------------", abc)
        # print("RAW_CLONE_URL:----------------", RAW_CLONE_URL)
        # print(type(abc))
        # print(type(RAW_CLONE_URL))

        if repo_url == RAW_CLONE_URL:
            print("  ↪ Root repo match. Executing full hydration steps...")

            # VCLUSTER_ARGOCD_PASSWORD = run_command(" kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode ", True)
            # VCLUSTER_ARGOCD_PASSWORD = get_argocd_password()
            
            print(f"curremt context is : ",run_command("kubectl config current-context",True))
            run_command(f"kubectl get applications -n argocd",True)
            # Step 1: revision Change to branch
            print("----------taget new--------",target_new)
            # patch_app_revision(app_name, target_branch,manifest)
            patch_app_revision(app_name, ROOT_MAIN_APPLN_TARGET_REVISION, manifest, NAMESPACE)
            print(f"  ✅ Target revision set to {ROOT_MAIN_APPLN_TARGET_REVISION}")
            
            # Step 2: Refresh
            # try:
            #     run_command(f"argocd app get {app_name} --refresh --server localhost:8080 --insecure", True)
            #     # refresh_app(app_name)
            #     print("  ✅ refreshed")
            # except subprocess.CalledProcessError as e:
            #     print(f"  ⚠️ refresh failed: {e.stderr}")
            refresh_app_with_retry(app_name, namespace=NAMESPACE)
            
            # Step 3: Disable controller
            disable_app_controller(NAMESPACE)
            print("  🚫 Controller disabled")           
            # manifest["spec"]["source"]["targetRevision"] = ROOT_MAIN_APPLN_TARGET_REVISION

            # Step 4: change to new branch
            patch_app_revision(app_name, target_new, manifest,NAMESPACE)
            print(f"  🔒 Revision changed to new branch: {target_new}")
                       
            # manifest["spec"]["source"]["targetRevision"] = "target_new"
        else:
            print(f" ↪ Non-root repo match. Executing partial hydration steps... for {app_name}")
            # disable_app_controller()
            # 242 1nd 244 in place of 240
            enable_app_controller(NAMESPACE)
            patch_app_revision(app_name, target_new, manifest,NAMESPACE)
            disable_app_controller(NAMESPACE)
    enable_app_controller(NAMESPACE) 
    # in_consolidate_call.main(FILE_SUFFIX)
    if FILE_SUFFIX == "target":
        APP_NAME_MATCH = APP_NAMES
    in_consolidate_backup.main(FILE_SUFFIX, TOKEN_VCLUSTER,APP_NAME_MATCH)
    
    if FILE_SUFFIX == "target":
        time.sleep(10)
    run_command("kubectl apply -f application.yaml",True)
    in_source.patch_app_revision("myapp-root-application", NAMESPACE)

    return APP_NAMES


    
    


        
