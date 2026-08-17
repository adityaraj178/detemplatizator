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


import fix
# INPUTS
# 1. repo_raw_url of manifest
# 2. BB_username
# 3. BB_password
# 4. Argo CD url/ OC url && namespace




urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def generate_secret_name():
    return f"bb-repo-{uuid.uuid4().hex[:6]}"

def generate_cluster_secret_name(name):
    return f"bb-{name}-{uuid.uuid4().hex[:6]}"

def generate_secret_name_for_cred_repo(name):
    return f"repo-cred-{name}-{uuid.uuid4().hex[:6]}"

# def run_command(command, capture_output=False):
#     result = subprocess.run(['C:\\Program Files\\Git\\bin\\bash.exe', '-c', command], shell=True, check=True, capture_output=capture_output, text=True)
#     return result.stdout.strip() if capture_output else None

def run_command_pws(command, capture_output=False):
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=capture_output,
            text=True
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e.cmd}")
        print(f"🔴 Return code: {e.returncode}")
        print(f"📝 Output: {e.output}")
        print(f"⚠️ Error: {e.stderr}")
        raise

def get_applications(ARGOCD_SERVER, HEADERS, VERIFY_SSL):
    url = f"{ARGOCD_SERVER}/api/v1/applications"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    # print("RESPONSE:", response.text)
    response.raise_for_status()
    return response.json()

def get_manifests(app_name, ARGOCD_SERVER, HEADERS, VERIFY_SSL):
    url = f"{ARGOCD_SERVER}/api/v1/applications/{app_name}/manifests"
    response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    response.raise_for_status()
    return response.json()

def apply_secret_yaml(yaml_content):
    result = subprocess.run(
        ['kubectl', 'apply', '-f', '-'],
        input=yaml_content,
        text=True,
        capture_output=True
    )
    if result.returncode != 0:
        print(f"❌ Failed to apply secret:\n{result.stderr}")
    else:
        print(f"✅ Secret applied:\n{result.stdout}")

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
        print("-----------------------------------> Check  "+result.stdoutdecode())
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

def extract_repo_creds_secret_data(secret):
    data = secret.get("data", {})
    return {
        "username": base64.b64decode(data.get("username", "")).decode(),
        "url": base64.b64decode(data.get("url", "")).decode(),
        "password": base64.b64decode(data.get("password", "")).decode(),
        "name": base64.b64decode(data.get("name", "")).decode()
    }

def get_argocd_secrets(namespace):
    cmd = ["oc", "get", "secrets", "-n", namespace, "-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    secrets = json.loads(result.stdout).get("items", [])

    repo_secrets = []
    cluster_secrets = []
    CRED_SECRETES = []

    for secret in secrets:
        labels = secret.get("metadata", {}).get("labels", {})
        secret_type = labels.get("argocd.argoproj.io/secret-type", "")

        if secret_type == "repository":
            repo_data = extract_repo_secret_data(secret)
            repo_secrets.append(repo_data)

        elif secret_type == "cluster":
            if secret.get("data", {}).get("name") == "aW4tY2x1c3Rlcg==":
                global CONFIG_IN_CLUSTER 
                global SERVER_IN_CLUSTER
                SERVER_IN_CLUSTER = secret.get("data", {}).get("server")
                # CONFIG_IN_CLUSTER=secret.get("data", {}).get("config")
                CONFIG_IN_CLUSTER = "abcdefghijkl" 
                # print(f"------------------var configured to {CONFIG_IN_CLUSTER}")
            # print(f"-------------------------cluster-extracted-info-raw----------->{secret}")
            cluster_data = extract_cluster_secret_data(secret)
            cluster_secrets.append(cluster_data)
        
        elif secret_type == "repo-creds":
            repo_creds_data= extract_repo_creds_secret_data(secret)
            CRED_SECRETES.append(repo_creds_data)

    return repo_secrets, cluster_secrets, CRED_SECRETES

def extract_repo_secret_data(secret):
    data = secret.get("data", {})
    return {
        "name": base64.b64decode(data.get("name", "")).decode(),
        "url": base64.b64decode(data.get("url", "")).decode(),
        "username": base64.b64decode(data.get("username", "")).decode(),
        "password": base64.b64decode(data.get("password", "")).decode(),
        "type": base64.b64decode(data.get("type", "")).decode(),
        "insecure": base64.b64decode(data.get("insecure", "")).decode(),
    }

def sanitize_manifest(manifest: dict):
    """
    Sanitizes a Kubernetes manifest by removing specific fields.

    Args:
        manifest (dict): The Kubernetes manifest to sanitize.

    Returns:
        dict: The sanitized manifest.
    """
    if "metadata" in manifest:  # Check if "metadata" key exists
        for field in ["uid", "resourceVersion", "creationTimestamp", "managedFields"]:
            manifest["metadata"].pop(field, None)
    return manifest

def dict_to_yaml(data, indent=0):
    """
    Converts a Python dictionary to a YAML-formatted string, handling nested structures.

    Args:
        data (dict): The dictionary to convert.
        indent (int, optional): The current indentation level. Defaults to 0.

    Returns:
        str: The YAML-formatted string.
    """
    yaml_string = ""
    if isinstance(data, dict):
        for key, value in data.items():
            yaml_string += " " * indent + f"{key}:"
            if isinstance(value, (dict, list)):
                yaml_string += "\n"
                yaml_string += dict_to_yaml(value, indent + 2)
            else:
                yaml_string += f" {value}\n"
    elif isinstance(data, list):
        for item in data:
            yaml_string += " " * indent + f"- "
            if isinstance(item, (dict, list)):
                yaml_string += "\n"
                yaml_string += dict_to_yaml(item, indent + 2)
            else:
                yaml_string += f"{item}\n"
    else:
        yaml_string += f"{data}\n"
    return yaml_string

def create_argocd_repo_secret(name, namespace, repo):
    """
    Creates a Kubernetes secret to store repository credentials using kubectl CLI.

    Args:
        name (str): The name of the secret.
        namespace (str): The namespace where the secret should be created.
        repo (dict): A dictionary containing the repository details, including:
            - url (str): The repository URL.
            - username (str, optional): The username for authentication.
            - password (str, optional): The password for authentication.
            - type (str, optional): The repository type (e.g., "git", "helm"). Defaults to "helm".
            - name (str, optional): Repository name. Defaults to "default-repo".
            - insecure (str, optional): "true" or "false".
    """
    # Construct the kubectl create secret command.
    command = [
        "kubectl",
        "create",
        "secret",
        "generic",
        name,
        f"--namespace={namespace}",
        f"--from-literal=url={repo['url']}",
        f"--from-literal=username={repo.get('username', '')}",  # Handle missing values
        f"--from-literal=password={repo.get('password', '')}",  # Handle missing values
    ]

    # Add optional parameters
    if repo.get("type"):
        command.append(f"--from-literal=type={repo['type']}")
    if repo.get("name"):
        command.append(f"--from-literal=name={repo['name']}")
    if repo.get("insecure"):
        command.append(f"--from-literal=insecure={repo['insecure']}")

    command.extend([
        "--dry-run=client",
        "-o",
        "yaml",
    ])

    # Add the label
    label_command = ["kubectl", "label", "-f-", "argocd.argoproj.io/secret-type=repository", "--local", "-o", "yaml"]
    apply_command = ["kubectl", "apply", "-f", "-"]
    try:
        # Use subprocess.Popen to pipe the output
        create_process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        label_process = subprocess.Popen(label_command, stdin=create_process.stdout, stdout=subprocess.PIPE, text=True)
        apply_process = subprocess.Popen(apply_command, stdin=label_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        create_process.wait()
        label_process.wait()
        apply_process.wait()

        if apply_process.returncode != 0:
            stderr_output = apply_process.stderr.read()
            print(f"Error applying secret:\n{stderr_output}")
            raise subprocess.CalledProcessError(apply_process.returncode, apply_command, stderr=stderr_output)
        else:
            print(f"Secret {name} created and applied successfully in namespace {namespace}")

    except Exception as e:
        print(f"An error occurred: {e}")
        raise

def extract_cluster_secret_data(secret):
    data = secret.get("data", {})
    return {
        "name": base64.b64decode(data.get("name", "")).decode(),
        "server": base64.b64decode(data.get("server", "")).decode(),
        "namespaces": base64.b64decode(data.get("namespaces", "")).decode(),
        "config": json.loads(base64.b64decode(data.get("config", "")).decode()),
        "clusterResources": base64.b64decode(data.get("clusterResources", "")).decode(),
    }

def unwrap(val):
    if isinstance(val, (list, tuple)) and len(val) == 1:
        return val[0]
    return val

def extract_cluster_secret_data_to_apply(secret):
    config_raw = secret.get("config", {})

    # Ensure config is parsed JSON
    if isinstance(config_raw, str):
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError:
            print("❌ Failed to decode config JSON")
            config = {}
    else:
        config = config_raw
    # No decoding needed — input is already parsed!
    name = secret.get("name", "")
    server = secret.get("server", "")
    token = unwrap(config.get("bearerToken", None))
    insecure = unwrap(config.get("tlsClientConfig", {}).get("insecure", True))
    namespaces = secret.get("namespaces", "")
    cluster_resources = secret.get("clusterResources", "false")

    return {
        "name": name,
        "server": server,
        "token": token,
        "insecure": insecure,
        "namespaces": namespaces,
        "clusterResources": cluster_resources,
    }

def create_repo_secret(namespace, url, username, password, secret_name):
    # Base64 encode the username and password.
    encoded_username = base64.b64encode(username.encode()).decode()
    encoded_password = base64.b64encode(password.encode()).decode()
    encoded_url = base64.b64encode(url.encode()).decode()
    encoded_true = base64.b64encode("true".encode()).decode()  # Encode "false" as a string
    # Define the Kubernetes Secret YAML structure as a Python dictionary.
    secret_yaml = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
            "labels": {
                "argocd.argoproj.io/secret-type": "repo-creds"  # Important label for Argo CD
            },
            "annotations": {
                "managed-by": "argocd.argoproj.io"
            }
        },
        "type": "Opaque",  # Use Opaque for generic secrets
        "data": {
            "insecure": encoded_true,
            "url": encoded_url,
            "username": encoded_username,
            "password": encoded_password,
        },
    }
    return secret_yaml

def apply_k8s_resource(yaml_data):
    """
    Applies a Kubernetes resource (e.g., a Secret) using kubectl.

    Args:
        yaml_data (dict): A dictionary representing the Kubernetes resource YAML.
    """
    # Convert the YAML data to a string.
    yaml_string = yaml.dump(yaml_data)

    # Use subprocess to run the kubectl apply command.
    cmd = ["kubectl", "apply", "-f", "-"]  # Apply from stdin
    try:
        process = subprocess.run(cmd, input=yaml_string, capture_output=True, text=True, check=True)
        print(f"Successfully applied: {yaml_data['metadata']['name']}")
        print(process.stdout) # print the output of the command
    except subprocess.CalledProcessError as e:
        print(f"Error applying resource: {yaml_data['metadata']['name']}")
        print(e.stderr)  # Print the error message from kubectl
        print(e.stdout)
        raise  # Re-raise the exception to stop execution if needed

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

def ensure_clusterrolebinding_exists(binding_name, service_account, namespace):
    try:
        # Check if the ClusterRoleBinding exists
        subprocess.run(
            ["kubectl", "get", "clusterrolebinding", binding_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"✅ ClusterRoleBinding '{binding_name}' already exists. Skipping creation.")
    except subprocess.CalledProcessError:
        print(f"🔧 Creating ClusterRoleBinding '{binding_name}'...")
        subprocess.run([
            "kubectl", "create", "clusterrolebinding", binding_name,
            "--clusterrole=cluster-admin",
            f"--serviceaccount={namespace}:{service_account}"
        ], check=True)
        print("✅ ClusterRoleBinding created successfully.")

def add_argocd_tls_cert(hostname, cert_filename, cert_folder):
    """
    Adds a TLS certificate to Argo CD for a specified hostname.

    Args:
        hostname (str): The hostname for which to add the TLS certificate (e.g., "bitbucket.gob.amadeus.net").
        cert_filename (str): The name of the certificate file (e.g., "bitbucket-fullchain.pem").
        cert_folder (str): The directory where the certificate file is located,
                           relative to where the Python script is run.
    """
    # Construct the full path to the certificate file
    # If cert_folder is "cert", and script is in parent, it naturally creates "cert/bitbucket-fullchain.pem"
    cert_filepath = os.path.join(cert_folder, cert_filename)

    # Check if the certificate file exists
    if not os.path.exists(cert_filepath):
        print(f"Error: Certificate file not found at '{cert_filepath}'")
        return

    command = [
        "argocd", "cert", "add-tls",
        hostname,
        "--from", cert_filepath
    ]

    print(f"Executing command: {' '.join(command)}")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("Command executed successfully!")
        print("STDOUT:\n", result.stdout)
        if result.stderr:
            print("STDERR:\n", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
    except FileNotFoundError:
        print("Error: 'argocd' command not found. Make sure Argo CD CLI is installed and in your PATH.")


def main(BB_USERNAME, BB_APP_PASSWORD, REPO_RAW_URL,NAMESPACE,OC_URL,OC_TOKEN,OC_NAMESPACE,OC_HTTPS_PROXY,HOST_CLUSTER_NAME):
    #should be in host-cluster ,  in start//this is start
    #vcluster connected before running this script
    print("----------------------------------->  CURRENT CONTEXT: ", run_command_pws("kubectl config current-context", True))

    # Validating that RAW_URL has been Passed as CLI input
    # if len(sys.argv) < 2:
    #     print("Usage: python deploy_argocd.py <repo_raw_url>")
    #     sys.exit(1)
    # REPO_RAW_URL = sys.argv[1].strip()



    # token=create_server_and_bearer_token(8081)
    token = OC_TOKEN
    # Getting configured repo list of host cluster through swagger ui
    # url = "https://localhost:8081/api/v1/repositories"
    url = OC_URL
    # os.environ["https_proxy"] = "https://acs-proxy.gob.amadeus.net/"
    os.environ["https_proxy"] = OC_HTTPS_PROXY
    run_command_pws(f"oc login --token={token} --server={url}", True)
    # OC_NAMESPACE = "argocd-demo-tst"
    REPO_URLS, CLUSTER_URLS, CRED_SECRETES = get_argocd_secrets(OC_NAMESPACE)
    run_command_pws(f"kubectl config use-context {HOST_CLUSTER_NAME}",True)
    os.environ.pop("https_proxy", None)
    os.environ.pop("HTTPS_PROXY", None)

    # PROBLEM: ASSUMED THAT THERE IS ONLY ONE VIRTUAL CLUSTER
    #need to switch context to virtual cluster
    HOST_CONTEXT = run_command_pws("kubectl config current-context",True)
    print(f"----------------------------------->  CURRENT CONTEXT: {HOST_CONTEXT}")
    vcluster_names = run_command_pws("vcluster list --output json", capture_output=True)
    # print("----------------------------------->  VCLUSTER ALL INFORMATION: ", vcluster_names)
    # VCLUSTER_NAME = run_command_pws("vcluster list | awk '/Running/ {print $1; exit}'", capture_output=True)
    # VCLUSTER_NAMESPACE= run_command_pws("vcluster list | awk '/Running/ {print $3; exit}'", capture_output=True)
    VCLUSTER_NAME="my-vcluster-test-15"
    VCLUSTER_NAMESPACE="vcluster-my-vcluster-test-15"

    VIRTUAL_CONTEXT = f"vcluster_{VCLUSTER_NAME}_{VCLUSTER_NAMESPACE}_{HOST_CONTEXT}"

    print(f"----------------------------------->  VCLUSTER_NAME: {VCLUSTER_NAME}, NAMESPACE: {VCLUSTER_NAMESPACE}, CONTEXT_NAME: {HOST_CONTEXT}")
    print(f"----------------------------------->  VIRTUAL CONTEXT:   {VIRTUAL_CONTEXT}")
    # connect to vcluster
    port_forward_proc = subprocess.Popen(f"vcluster connect {VCLUSTER_NAME}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 2: Poll until the vcluster API server is reachable
    print(f"⏳ Waiting for vcluster context '{VIRTUAL_CONTEXT}' to be ready...")
    max_retries = 30
    for attempt in range(max_retries):
        try:
            test_cmd = f"kubectl get ns --context {VIRTUAL_CONTEXT}"
            result = run_command_pws(test_cmd, True)
            if result and "NAME" in result:
                print("✅ vcluster is ready.")
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        print("❌ Timeout waiting for vcluster to be ready.")
        port_forward_proc.terminate()
        exit(1)

    run_command_pws(f"kubectl config use-context {VIRTUAL_CONTEXT}", capture_output=True)
    print("----------------------------------->  CURRENT CONTEXT: ", run_command_pws("kubectl config current-context", True))

    # Namespce creation and argocd installation will be done by create-vcluster.sh script
    # run_command_pws(f"kubectl create namespace {NAMESPACE}", capture_output=True)
    # ensure_namespace(NAMESPACE)
    # print(f"----------------------------------->  NAMESPACE CREATED: {NAMESPACE}")
    # install argocd in vcluster
    # run_command_pws(f"kubectl apply -n {NAMESPACE} -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml", capture_output=True)
    # run_command_pws(
    # f"curl -sSL https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml | kubectl apply -n {NAMESPACE} -f -",
    # capture_output=True)
    # ensure_argo_cd_installed(NAMESPACE)
    # kubectl create clusterrolebinding argocd-application-controller-cluster-admin --clusterrole=cluster-admin --serviceaccount=argocd-demo-tst:argocd-application-controller

    # run_command_pws(f"kubectl create clusterrolebinding argocd-application-controller-cluster-admin --clusterrole=cluster-admin --serviceaccount={NAMESPACE}:argocd-application-controller", capture_output=True)
    # Example usage

    TOKEN_VCLUSTER, VCLUSTER_ARGOCD_PASSWORD = fix.create_server_and_bearer_token(8080,NAMESPACE)

    ensure_clusterrolebinding_exists(binding_name="argocd-application-controller-cluster-admin",service_account="argocd-application-controller",namespace=NAMESPACE)

    # Code to add 
    # PROBLEM: need argocd 
    
    add_argocd_tls_cert(
        hostname="bitbucket.gob.amadeus.net",
        cert_filename="bitbucket-fullchain.pem",
        cert_folder="certificates"
    )

    # kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
    print(f"----------------------------------->  ARGOCD INSTALLED IN NAMESPACE: {NAMESPACE}")




    #------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # CREATING SECRET FOR EACH REPO_URL
    # NAMESPACE = "argocd"
    for repo in REPO_URLS:  
        REPO_URL = repo["url"]
        SECRET_NAME = generate_secret_name()

        print(f"-----------------------------------> CREATING SECRET FOR REPO: {REPO_URL} -> Secret: {SECRET_NAME} IN CONTEXT: ", run_command_pws("kubectl config current-context", True))

        # create_secret_cmd = (
        #     f"kubectl create secret generic {SECRET_NAME} "
        #     f"--namespace {NAMESPACE} "
        #     f"--from-literal=url='{REPO_URL}' "
        #     f"--from-literal=username='{repo['username']}' "
        #     f"--from-literal=password='{repo['password'].replace('\'', '\\\'')}' "
        #     f"--from-literal=type='{repo['type']}' "
        #     f"--from-literal=name='{repo['name']}' "
        #     f"--from-literal=insecure='{repo['insecure']}' "
        #     f"--dry-run=client -o yaml | "
        #     f"kubectl label -f - argocd.argoproj.io/secret-type=repository --local -o yaml | "
        #     f"kubectl apply -f -"
        # )
        # run_command(create_secret_cmd)
        repo = {
            "url": REPO_URL,
            "username": str(repo.get("username", "")),
            "password": str(repo.get("password", "")),
            "type": str(repo.get("type", "helm")),
            "name": str(repo.get("name", "helm-repo")),
            "insecure": str(repo.get("insecure", ""))
        }
        create_argocd_repo_secret(SECRET_NAME, NAMESPACE, repo)

    # CREATING SECRET FOR EACH REPO_CRED
    #------------------------------------------------------------------------------------------------------------------------------------------------------------------------




    for cred_secret in CRED_SECRETES:
        url = cred_secret["url"]
        username = cred_secret["username"]
        password = cred_secret["password"]
        name = cred_secret["name"]  # Get the repo name
        secret_name = generate_secret_name_for_cred_repo(name) # Generate Secret Name
        print(f"-----------------------{url}---{username}------{password}------{name}------{secret_name}")
        print(f"-----------------------------------> CREATING SECRET {secret_name} FOR {url}")

        # Create the Kubernetes Secret YAML.
        secret_yaml = create_repo_secret(NAMESPACE, url, username, password, secret_name)

        # Apply the secret to the Kubernetes cluster.
        apply_k8s_resource(secret_yaml)

    #------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # CREATING SECRET FOR EACH CLUSTER

    # Example: CLUSTER_SECRETS is a list of secrets returned from `kubectl get secrets -o json`
    for cluster_secret in CLUSTER_URLS:
        # if cluster_secret.get("name")=="nld11":
        #     print("----------------------------------->  CLUSTER SECRET:")
        #     print(f"------{cluster_secret}")
        store = extract_cluster_secret_data_to_apply(cluster_secret)
        # if cluster_secret.get("name")=="nld11":
            # print("---------------🔍 Extracted cluster secret data:")
            # print("-------------->",store)

        if not all(k in store for k in ("name", "server", "token")):
            print(f"⚠️ Skipping cluster due to missing keys: {store}")
            continue

        SECRET_NAME = generate_cluster_secret_name(store["name"])

        if cluster_secret.get("name")=="nld11":
            print(store)
            print(f"🔐 Creating ArgoCD secret for cluster: {SECRET_NAME}")

        config_obj = {
            "bearerToken": store["token"],
            "tlsClientConfig": {"insecure": store["insecure"]}
        }
        # Use compact separators to avoid whitespace
        compact_json = json.dumps(config_obj, separators=(',', ':'))
        # if cluster_secret.get("name")=="nld11":
            # print("🔍 Config object:",config_obj)
        # Encode data
        encoded_config = base64.b64encode(compact_json.encode()).decode()
        encoded_name = base64.b64encode(store["name"].encode()).decode()
        encoded_server = base64.b64encode(store["server"].encode()).decode()
        encoded_namespaces = base64.b64encode(store["namespaces"].encode()).decode()
        encoded_cluster_resources = base64.b64encode(store["clusterResources"].encode()).decode()
        # if cluster_secret.get("name")=="nld11":
            # print("🔍 Encoded config:",encoded_config)
        # YAML manifest
        secret_yaml = f"""
apiVersion: v1
kind: Secret
metadata:
  name: {SECRET_NAME}
  namespace: {NAMESPACE}
  labels:
    argocd.argoproj.io/secret-type: cluster
type: Opaque
data:
  name: {encoded_name}
  server: {SERVER_IN_CLUSTER}
  config: {CONFIG_IN_CLUSTER}
  namespaces: ""
  clusterResources: {encoded_cluster_resources}
"""
        # if cluster_secret.get("name")=="nld11":
            # print(f"---------------------\n",secret_yaml)
        time.sleep(1)
        apply_secret_yaml(secret_yaml)


    #------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    os.environ.pop("HTTPS_PROXY", None)
    # ROOT_MAIN_APPLN_TARGET_REVISION = in_source.caller(REPO_RAW_URL, BB_USERNAME, BB_APP_PASSWORD)
    # extracting raw manifest for appln creation
    # CRED = base64.b64encode(f"{BB_USERNAME}:{BB_APP_PASSWORD}".encode()).decode()
    # app_url = f"{REPO_RAW_URL}"
    # header_appln = {"Authorization": f"Basic {CRED}"}
    # response_appln = requests.get(app_url, headers=header_appln, verify=False)

    # if response_appln.status_code == 200:
    #     with open("application.yaml", "w") as f:
    #         f.write(response_appln.text)
    #     run_command("kubectl apply -f application.yaml")
    #     print("----------------------------------->  application.yaml successfully applied.")
    # else:
    #     print(f"----------------------------------->  Failed to download application.yaml: HTTP {response_appln.status_code}")

    # print ("----------------------------------->  EXIT , CURRENT CONTEXT: ", run_command("kubectl config current-context",True))

    # run_command("kubectl apply -f application.yaml")




    #------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # GENERATING HYDATED MANIFESTS FOR ALL APPLICATIONS
    ###############  TRYING TO CONSOLIDATE MANIFEST FOR APPLICATIONS  #######################
    # -----------NO NEED FOR NOW---------------

    # TOKEN_VCLUSTER=create_server_and_bearer_token(8080)
    # ARGOCD_SERVER = "https://localhost:8080"
    # VERIFY_SSL = False
    # HEADERS = {
    # 'Authorization': f'Bearer {TOKEN_VCLUSTER}',
    # 'Accept': 'application/json',
    # }


    # combined_yaml_docs = []
    # time.sleep(2)
    # # Step 1: Get all applications
    # apps_response = get_applications(ARGOCD_SERVER, HEADERS, VERIFY_SSL)
    # app_items = apps_response.get("items", [])
    # APP_NAMES = []
    # for i in app_items:
    #     print("----------------------------------->  APPLICATIONS: ",i.get("metadata", {}).get("name"))
    #     APP_NAMES.append(i.get("metadata", {}).get("name"))
        
    # # Step 2: For each app, fetch its manifestss
    # for app in app_items:
    #     app_name = app.get("metadata", {}).get("name")
    #     if app_name:
    #         print(f"Fetching manifests for app: {app_name}")
    #         manifest_response = get_manifests(app_name, ARGOCD_SERVER, HEADERS, VERIFY_SSL)
    #         manifests = manifest_response.get("manifests", [])
            
    #         # Step 3: Convert each manifest JSON string -> Python dict -> YAML string
    #         for manifest_json in manifests:
    #             manifest_dict = yaml.safe_load(manifest_json)  # convert JSON to dict
    #             manifest_yaml = yaml.dump(manifest_dict, sort_keys=False)  # dict to YAML
    #             combined_yaml_docs.append(manifest_yaml.strip())

    # # Step 4: Combine all YAMLs
    # final_output = "\n\n---\n\n".join(combined_yaml_docs)

    # # Step 5: Write to a file
    # with open("combined_manifests.yaml", "w") as f:
    #     f.write(final_output)

    # print("Combined YAML manifests written to 'combined_manifests.yaml'.")



    # port_forward_proc.terminate() 

    # return ROOT_MAIN_APPLN_TARGET_REVISION

    return TOKEN_VCLUSTER, VCLUSTER_ARGOCD_PASSWORD


def caller_function (BB_USERNAME, BB_APP_PASSWORD, REPO_RAW_URL, NAMESPACE,OC_URL,OC_TOKEN,OC_NAMESPACE, OC_HTTPS_PROXY,HOST_CLUSTER_NAME):
    print("executing test-deploy-app")
    return main(BB_USERNAME, BB_APP_PASSWORD, REPO_RAW_URL, NAMESPACE,OC_URL,OC_TOKEN,OC_NAMESPACE, OC_HTTPS_PROXY,HOST_CLUSTER_NAME)
    # print("exiting test_deploy_app")

