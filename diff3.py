import yaml
from collections import defaultdict
import difflib

def normalize_doc(doc):
    """Remove fields that are not relevant for diffing"""
    if not doc:
        return doc
    # print("in the function of normalization")

    kind = doc.get("kind", "Application")
    # print("kind: ", kind)
    if kind == "Application":
        # print("in the if cmd of normalization")
        
        # Clean known dynamic fields
        source = doc.get("spec", {}).get("source", {})
        if "targetRevision" in source:
            source["targetRevision"] = "<normalized>"
        if "repoURL" in source:
            source["repoURL"] = "<normalized>"
        # if "namespace" in doc.get("spec",{}).get("destination",{}):
        #     doc["spec"]["destination"]["namespace"]="<normalized>"

        doc.pop("status", None)
        # print(doc.get("status", {}))
        source = doc.get("status", {}).get("sync", {}).get("comparedTo", {}).get("source", {})
        if "targetRevision" in source:
            source["targetRevision"] = "<normalized>"
        if "repoURL" in source:
            source["repoURL"] = "<normalized>"
        
        sources = doc.get("spec", {}).get("sources", {})
        for source in sources:
            if "helm" not in source and  "targetRevision" in source:
                source["targetRevision"] = "<normalized>"
            if "helm" not in source and "repoURL" in source:
                source["repoURL"] = "<normalized>"

        # You can also clean status fields or annotations if needed
        doc.get("spec", {}).pop("status", None)
        doc.get("status", {}).pop("health", None)
        doc.get("status", {}).pop("history", None)
        doc.get("status", {}).pop("operationState", None)
        doc.get("status",{}).pop("reconciledAt", None)
        doc.get("status", {}).get("sync",{}).pop("revision", None)
        

        # Optional: ignore auto-generated status or sync fields
        # doc.pop("metadata",None)
        for field in list(doc.get("metadata", {}).keys()):
            if field.startswith("name") or field.startswith("namespace") or field.startswith("labels"):
                continue
            else:
                doc["metadata"].pop(field, None)
        doc.pop("operation", None)

    elif kind == "ApplicationSet":
        print("in the elif cmd of normalization")
        # Clean known dynamic fields for ApplicationSet
        source = doc.get("spec", {}).get("template", {}).get("spec", {}).get("source", {})
        if "repoURL" in source:
            source["repoURL"] = "<normalized>"
        # code to write
        # doc.get("metadata", {}).pop("annotations", None)
    # if doc.get("metadata",{}).get("name","")=="change-mgt-app-dev":
    #     print(doc)
    return doc


def test_normalize(doc):
    """Remove fields that are not relevant for diffing"""
    if not doc:
        return doc
    # print("in the function of normalization")

    kind = doc.get("kind", "Application")
    # print("kind: ", kind)
    if kind == "Application":
        # print("in the if cmd of normalization")
        
        # Clean known dynamic fields
        source = doc.get("spec", {}).get("source", {})
        if "targetRevision" in source:
            source["targetRevision"] = "<normalized>"
        if "repoURL" in source:
            source["repoURL"] = "<normalized>"
        if "namespace" in doc.get("spec",{}).get("destination",{}):
            doc["spec"]["destination"]["namespace"]="<normalized>"

        doc.pop("status", None)
        # print(doc.get("status", {}))
        source = doc.get("status", {}).get("sync", {}).get("comparedTo", {}).get("source", {})
        if "targetRevision" in source:
            source["targetRevision"] = "<normalized>"
        if "repoURL" in source:
            source["repoURL"] = "<normalized>"
        
        sources = doc.get("spec", {}).get("sources", {})
        for source in sources:
            if "helm" not in source and  "targetRevision" in source:
                source["targetRevision"] = "<normalized>"
            if "helm" not in source and "repoURL" in source:
                source["repoURL"] = "<normalized>"

        # You can also clean status fields or annotations if needed
        doc.get("spec", {}).pop("status", None)
        doc.get("status", {}).pop("health", None)
        doc.get("status", {}).pop("history", None)
        doc.get("status", {}).pop("operationState", None)
        doc.get("status",{}).pop("reconciledAt", None)
        doc.get("status", {}).get("sync",{}).pop("revision", None)
        

        # Optional: ignore auto-generated status or sync fields
        # doc.pop("metadata",None)
        for field in list(doc.get("metadata", {}).keys()):
            if field.startswith("name") or field.startswith("namespace") or field.startswith("labels"):
                continue
            else:
                doc["metadata"].pop(field, None)
        doc.pop("operation", None)

    elif kind == "ApplicationSet":
        print("in the elif cmd of normalization")
        # Clean known dynamic fields for ApplicationSet
        source = doc.get("spec", {}).get("template", {}).get("spec", {}).get("source", {})
        if "repoURL" in source:
            source["repoURL"] = "<normalized>"
        if "targetRevision" in source:
            source["targetRevision"] = "<normalized>"
        doc.get("spec", {}).get("template",{}).get("spec",{}).get("destination", {}).pop("namespace", None)
        # code to write
        doc.get("metadata", {}).pop("annotations", None)
        generators = doc.get("spec", {}).get("generators", [])
        for element in generators:
            if "git" in element:
                print("in the git element of normalization")
                element["git"].pop("repoURL", None)
                element["git"].pop("revision", None)
            elif "list" in element:
                element["list"].pop("elements", None)
            elif "clusters" in element:
                element["clusters"].pop("selector", None)
                element["clusters"].pop("template", None)
            elif "matrix" in element:
                for matrix_element in element.get("matrix", {}).get("generators", []):
                    if "git" in matrix_element:
                        print("in the git element of matrix normalization")
                        matrix_element["git"].pop("repoURL", None)
                        matrix_element["git"].pop("revision", None)
        specs = doc.get("spec", {}).get("template", {}).get("spec", {}).get("sources", [])
        for spec in specs:
            if "helm" not in spec and "repoURL" in spec:
                spec["repoURL"] = "<normalized>"
            if "helm" not in spec and "targetRevision" in spec:
                spec["targetRevision"] = "<normalized>"
        doc.get("spec",{}).get("template",{}).get("metadata",{}).pop("name",None)
    # if doc.get("metadata",{}).get("name","")=="change-mgt-app-dev":
    #     print(doc)
    return doc

# def get_owner_and_destination(doc):
#     owner = "-"
#     dest_ns = "-"
#     dest_name = "-"
#     # Extract Application name from ownerReferences
#     refs = doc.get("metadata", {}).get("ownerReferences", [])
#     if refs and isinstance(refs, list):
#         owner = refs[0].get("name", "-")
    
#     # Extract destination
#     dest = doc.get("spec", {}).get("destination", {})
#     dest_ns = dest.get("namespace", "-")
#     dest_name = dest.get("name", "-")
    
#     return owner, dest_ns, dest_name

def load_documents_by_key(filepath):
    with open(filepath) as f:
        docs = list(yaml.safe_load_all(f))
        # print("---------------")
        # print(docs)
 
    # docs_by_key = defaultdict(dict)
    docs_by_key = {}
    for i, doc in enumerate(docs):
        if not doc:
            continue
        #  NORMALIZATION
        kind = doc.get("kind","Application")
        name = doc.get("metadata", {}).get("name")
        # doc = normalize_doc(doc)
        # print("kind: ", kind)
        # print("name: ", name)   
        if kind and name:
            key = f"{kind}/{name}"
        else:
            key = f"index_{i}"
        docs_by_key[key] = doc
    return docs_by_key
 

def extract_app_deployments(docs):
    app_map = {}
    for doc in docs.values():
        # print(doc.get("kind"))
        if doc.get("kind","") == "":
            # print("inside")
            app_name = doc.get("metadata", {}).get("name", "-")
            destination = doc.get("spec", {}).get("destination", {})
            cluster = destination.get("name") or destination.get("server", "-")
            namespace = destination.get("namespace", "-")
            app_map[app_name] = {
                "cluster": cluster,
                "namespace": namespace
            }
    return app_map

def diff_yaml_docs_silented_for_now(file1, file2):
    docs1 = load_documents_by_key(file1)
    docs2 = load_documents_by_key(file2)

    app_deployments = extract_app_deployments({**docs1, **docs2})

    output = ""
    all_keys = set(docs1.keys()).union(docs2.keys())

    for key in sorted(all_keys):
        doc1 = docs1.get(key)
        doc2 = docs2.get(key)

        active_doc = doc1 or doc2
        app_owner, dest_ns, dest_name = get_owner_and_destination(active_doc)

        if app_owner == "-":
            if doc1 or doc2 :
                labels = (doc1 or doc2).get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
                app_owner = labels.split("/")[0].split(":")[0] if labels else "-"
                dest_ns = labels.split("/")[1].split(":")[1] if labels else "-"
    


        header = f"""🔍 Diff for manifest: ({key})
Deployed by: {app_owner}
Target destination:
    namespace={dest_ns}
    name={dest_name}
"""

        header_no_diff = f"""✅ No differences for manifest: ({key})
Deployed by: {app_owner}
Target destination: 
    namespace={dest_ns}
    name={dest_name}
"""

        if doc1 is None:
            output += f"\n🟡 Present only in {file2}: {key}\n"
            if "spec" in doc2 and "destination" in doc2["spec"]:
                output += yaml.dump({"spec": {"destination": doc2["spec"]["destination"]}}, sort_keys=False) + "\n"
            continue

        if doc2 is None:
            output += f"\n🟡 Present only in {file1}: {key}\n"
            if "spec" in doc1 and "destination" in doc1["spec"]:
                output += yaml.dump({"spec": {"destination": doc1["spec"]["destination"]}}, sort_keys=False) + "\n"
            continue

        yaml1 = yaml.dump(doc1, sort_keys=True).splitlines(keepends=True)
        yaml2 = yaml.dump(doc2, sort_keys=True).splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            yaml1,
            yaml2,
            fromfile=f"{file1}:{key}",
            tofile=f"{file2}:{key}",
            lineterm=""
        ))

        # Filter only actual change lines
        changed_lines = [line for line in diff if line.startswith("+") or line.startswith("-")]
        changed_lines = [line for line in changed_lines if not line.startswith("+++ ") and not line.startswith("--- ")]

        if changed_lines:
            output += header
            output += ''.join(changed_lines)
            output += "\n\n"
        else:
            output += header_no_diff + "\n\n"

    return output


def diff_yaml_docs(file1, file2):
    docs1 = load_documents_by_key(file1)
    docs2 = load_documents_by_key(file2)

    # Combine for app lookup
    app_deployments = extract_app_deployments({**docs1, **docs2})

    output = ""
    all_keys = set(docs1.keys()).union(docs2.keys())

    for key in sorted(all_keys):
        doc1 = docs1.get(key)
        doc2 = docs2.get(key)

        # Only in target
        if doc1 is None:
            tracking_id = doc2.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
            if tracking_id:
                app_name = tracking_id.split(":")[0] if tracking_id else "-"
            else:
                app_name = doc2.get("metadata", {}).get("name", "-")
            app_name = tracking_id.split(":")[0] if tracking_id else "-"
            dest = app_deployments.get(app_name, {})
            output += f"\n🆕Present only in {file2}: {key}\n"
            output += f"Deployed by: {app_name}\n"
            output += f"Target destination:\n\tcluster={dest.get('cluster', '-')}\n\tnamespace={dest.get('namespace', '-')}\n"
            # spec = doc2.get("spec", {})
            # output += yaml.dump({"spec": spec}, sort_keys=True) + "\n"
            continue

        # Only in source
        if doc2 is None:
            tracking_id = doc1.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
            if tracking_id:
                app_name = tracking_id.split(":")[0] if tracking_id else "-"
            else:
                app_name = doc1.get("metadata", {}).get("name", "-")
            print("app_name: ", app_name)
            dest = app_deployments.get(app_name, {})
            output += f"\n🆕Present only in {file1}: {key}\n"
            output += f"Deployed by: {app_name}\n"
            output += f"Target destination:\n\tcluster={dest.get('cluster', '-')}\n\tnamespace={dest.get('namespace', '-')}\n"
            # spec = doc1.get("spec", {})
            # output += yaml.dump({"spec": spec}, sort_keys=True) + "\n"
            continue

        # Both exist, compute diff
        tracking_id = doc1.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
        if tracking_id:
            app_name = tracking_id.split(":")[0] if tracking_id else "-"
        else:
            app_name = doc1.get("metadata", {}).get("name", "-")
        dest = app_deployments.get(app_name, {})

        doc1= test_normalize(doc1)
        doc2= test_normalize(doc2)

        yaml1 = yaml.dump(doc1 or {}, sort_keys=True).splitlines(keepends=True)
        yaml2 = yaml.dump(doc2 or {}, sort_keys=True).splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            yaml1, yaml2,
            fromfile=f"{file1}:{key}",
            tofile=f"{file2}:{key}",
            lineterm="\n"
        ))

        if diff:
            output += f"\n🔁manifest for : ({key}) is updated\n"
            output += f"Deployed by: {app_name}\n"
            output += f"Target destination:\n\tcluster={dest.get('cluster', '-')}\n\tnamespace={dest.get('namespace', '-')}\n"
            for line in diff:
                if line.startswith("+") or line.startswith("-"):
                    output += line 
            output += ""
        # else:
        #     output += f"\n✅ No differences for manifest: ({key})\n"

    return output

 
# Example usage
def main():
    output = diff_yaml_docs('combined_manifests_source.yaml', 'combined_manifests_target.yaml')
    # output = diff_yaml_docs('combined_manifests_target.yaml', 'combined_manifests_source.yaml')
    with open('diff3_output.diff', 'w', encoding="utf-8") as f:
        f.write(output)
        print("✅ Diff written to diff3_output.diff")


if __name__ == "__main__":
    main()