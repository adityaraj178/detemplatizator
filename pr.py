import subprocess
import requests
import re
import os
import sys

# Give PR_URL as CLI input
BITBUCKET_BASE = os.getenv("BITBUCKET_BASE_URL")
if not BITBUCKET_BASE:
    raise ValueError("Environment variable BITBUCKET_BASE_URL is not set")
REPO_DIR = "my-repo"

# extracting username from env var
BB_USERNAME = os.getenv("BB_USERNAME")
if not BB_USERNAME:
    raise ValueError("Environment variable BB_USERNAME is not set")

# extracting pswd from env var
BB_APP_PASSWORD = os.getenv("BB_APP_PASSWORD")
if not BB_APP_PASSWORD:
    raise ValueError("Environment variable BB_APP_PASSWORD is not set")

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

# original
# https://bitbucket.example.net/projects/ARGOCD/repos/demo-deployments-env/pull-requests/77/overview
# local
# https://bitbucket.example.net/users/raj/repos/demo-deployments-env/pull-requests/1/overview
def parse_pr_url(pr_url):
    """
    Handles both project-based and user-based Bitbucket PR URLs.
    """
    base = re.escape(BITBUCKET_BASE)
    project_pattern = rf"{base}/projects/([^/]+)/repos/([^/]+)/pull-requests/(\d+)"
    user_pattern = rf"{base}/users/([^/]+)/repos/([^/]+)/pull-requests/(\d+)"

    project_match = re.match(project_pattern, pr_url)
    user_match = re.match(user_pattern, pr_url)

    if project_match:
        owner_type = "project"
        project, repo, pr_id = project_match.groups()
    elif user_match:
        owner_type = "user"
        project, repo, pr_id = user_match.groups()
        project=f"~{project}"
    else:
        raise ValueError("Invalid PR URL format")
    print(f"Project name: {project}")
    return project, repo, pr_id

# local
# https://bitbucket.example.net/rest/api/latest/projects/~PARAJ5/repos/demo-deployments-env-based/pull-requests/1?avatarSize=48&markup=true
# original
# https://bitbucket.example.net/rest/api/latest/projects/ARGOCD/repos/demo-deployments-env-based/pull-requests/77?avatarSize=48&markup=true
def get_pr_details(project, repo, pr_id):
    api_url = f"{BITBUCKET_BASE}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}"
    response = requests.get(api_url, auth=(BB_USERNAME, BB_APP_PASSWORD), verify=False)
    response.raise_for_status()
    pr_data = response.json()
    source_branch = pr_data["fromRef"]["displayId"]
    target_branch = pr_data["toRef"]["displayId"]
    source_commit = run_command(f"git ls-remote {BITBUCKET_BASE}/scm/{project}/{repo}.git {source_branch}", capture_output=True).split()[0]
    target_commit = run_command(f"git ls-remote {BITBUCKET_BASE}/scm/{project}/{repo}.git {target_branch}", capture_output=True).split()[0]
    # this will point to original repo not to forked repo
    # SOURCE_REPO_CLONE_URL = pr_data.get("fromRef", {}).get("repository", {}).get("origin", {}).get("links", {}).get("clone", [{}])[0].get("href")
    # TARGET_REPO_CLONE_URL = pr_data.get("toRef", {}).get("repository", {}).get("origin", {}).get("links", {}).get("clone", [{}])[0].get("href")

    source_repo_name = pr_data.get("fromRef", {}).get("repository", {}).get("name", "")
    target_repo_name = pr_data.get("toRef", {}).get("repository", {}).get("name", "")
    SOURCE_REPO_CLONE_URL = f"{BITBUCKET_BASE}/scm/{project.lower()}/{source_repo_name}.git"
    TARGET_REPO_CLONE_URL = f"{BITBUCKET_BASE}/scm/{project.lower()}/{target_repo_name}.git"
    

    return source_branch, target_branch, source_commit, target_commit, SOURCE_REPO_CLONE_URL, TARGET_REPO_CLONE_URL

def clone_or_fetch_repo(project, repo):
    repo_url = f"{BITBUCKET_BASE}/scm/{project.lower()}/{repo}.git"
    if os.path.exists(REPO_DIR):
        print(f"Directory {REPO_DIR} already exists. Fetching latest changes...")
        subprocess.run(["git", "-C", REPO_DIR, "fetch"], check=True)
    else:
        print(f"Cloning repository {repo_url} into {REPO_DIR}...")
        subprocess.run(["git", "clone", repo_url, REPO_DIR], check=True)
    return repo_url

def branch_exists(branch_name):
    result = subprocess.run(
        ["git", "-C", REPO_DIR, "branch", "--list", branch_name],
        capture_output=True, text=True
    )
    return branch_name in result.stdout.strip()

def create_branch(base_branch, new_branch):
    subprocess.run(["git", "-C", REPO_DIR, "stash"], check=True)
    subprocess.run(["git", "-C", REPO_DIR, "checkout", base_branch], check=True)
    if branch_exists(new_branch):
        print(f"⚠️ Branch '{new_branch}' already exists. Switching to it.")
        subprocess.run(["git", "-C", REPO_DIR, "checkout", new_branch], check=True)
    else:
        subprocess.run(["git", "-C", REPO_DIR, "checkout", "-b", new_branch], check=True)
        subprocess.run(["git", "-C", REPO_DIR, "push", "--set-upstream", "origin", new_branch], check=True)
        print(f"✅ Created new branch '{new_branch}' from '{base_branch}'.")



def main(pr_url):
    print("PR URL:", pr_url)
    project, repo, pr_id = parse_pr_url(pr_url)
    print(f"Parsed PR URL: project={project}, repo={repo}, pr_id={pr_id}")

    source_branch, target_branch, source_commit, target_commit, TARGET_REPO_CLONE_URL, SOURCE_REPO_CLONE_URL= get_pr_details(project, repo, pr_id)
    print(f"Source branch: {source_branch}, Target branch: {target_branch}")
    print(f"Source commit: {source_commit}, Target commit: {target_commit}")
    print(f"SOURCE_REPO_CLONE_URL----->{SOURCE_REPO_CLONE_URL}")
    print(f"TARGET_REPO_CLONE_URL----->{TARGET_REPO_CLONE_URL}")

    # Clone or fetch the repository
    cloned_repo_url=clone_or_fetch_repo(project, repo)

    # Create new branches based on the PR details
    source_new = f"hydration-src-{pr_id}-{source_branch}-{source_commit}"
    target_new = f"hydration-dst-{pr_id}-{target_branch}-{target_commit}"
    print(f"Creating new branches: {source_new}, {target_new}")
    create_branch(source_branch, source_new)
    create_branch(target_branch, target_new)

    # need to get the head commit of the source branch and target branch    

    return source_new, target_new, source_branch, target_branch, SOURCE_REPO_CLONE_URL, TARGET_REPO_CLONE_URL, project, repo, pr_id
    # run_hydration(source_new, target_new)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pr_handler.py <PR_URL>")
        sys.exit(1)
    pr_url = sys.argv[1]
    main(pr_url)
