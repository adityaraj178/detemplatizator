FROM dockerhub.rnd.example.net/registry-1-docker-io-remote/ubuntu:latest

USER root

# Base environment
ENV OC4_VERSION=4.4.9
ENV OC4_DIR=/ocDir
ENV KUBECONFIG=/ocDir/config
ENV HOME=/ocDir

# Directories
RUN mkdir -p ${OC4_DIR} /default /config /secrets /app /my-repo /.kube

# Touch required files
RUN touch ${OC4_DIR}/listapps.txt ${OC4_DIR}/automated.txt ${OC4_DIR}/config ${OC4_DIR}/flow \
    ${OC4_DIR}/argocd_url ${OC4_DIR}/git_repo ${OC4_DIR}/commit_id ${OC4_DIR}/target_branch_list \
    ${OC4_DIR}/secret_name ${OC4_DIR}/script ${OC4_DIR}/timeout ${OC4_DIR}/delay \
    ${OC4_DIR}/dest_commit_id ${OC4_DIR}/source_branch_changes_required \
    ${OC4_DIR}/configuration_type ${OC4_DIR}/pre_validation ${OC4_DIR}/post_validation

# Install shell & system deps
RUN apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update -y && \
    apt-get install -y curl wget vim bash gzip git jq openjdk-21-jdk build-essential \
    ca-certificates conntrack iptables sudo python3 python3-pip python3-venv

# Python requirements
COPY requirements.txt /tmp/requirements.txt

RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r /tmp/requirements.txt



# Install oc
# Change it
RUN wget -nv https://repository.example.net/acs-project/openshift/client/linux/${OC4_VERSION}/oc-${OC4_VERSION}-linux.tar.gz --no-check-certificate && \
    tar -xvf oc-${OC4_VERSION}-linux.tar.gz -C ${OC4_DIR} && \
    rm oc-${OC4_VERSION}-linux.tar.gz && \
    mv ${OC4_DIR}/oc /usr/bin

# Install ArgoCD + Argo Workflows
RUN wget https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64 --no-check-certificate && \
    chmod +x argocd-linux-amd64 && mv argocd-linux-amd64 /usr/bin/argocd && \
    wget https://github.com/argoproj/argo-workflows/releases/download/v3.6.2/argo-linux-amd64.gz --no-check-certificate && \
    gzip -d argo-linux-amd64.gz && chmod +x argo-linux-amd64 && mv argo-linux-amd64 /usr/bin/argo

RUN curl -k -LO "https://cdn.dl.k8s.io/release/v1.33.1/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && mv kubectl /usr/local/bin/

# Install kind
RUN curl -k -Lo kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64 && \
    chmod +x kind && mv kind /usr/local/bin/kind

# Install vcluster
RUN curl -k -L https://github.com/loft-sh/vcluster/releases/latest/download/vcluster-linux-amd64 -o /usr/local/bin/vcluster && \
    chmod +x /usr/local/bin/vcluster

#change the below line to copy your own certificate if needed
COPY certificates/confidential.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# Copy hydration app code
COPY . /APP2
WORKDIR /APP2

# Optional: expose port if hydration UI or ArgoCD is hosted inside
EXPOSE 8080

# Set permissions
RUN chown -R 1001:0 ${OC4_DIR} /APP2 && chmod -R ug+rwX ${OC4_DIR} /APP2

# Environment variables — override all of these at runtime, never hardcode real values here
ENV BB_USERNAME="" \
    BB_APP_PASSWORD="" \
    BITBUCKET_BASE_URL="" \
    OC_HTTPS_PROXY="" \
    OC_NAMESPACE="" \
    OC_TOKEN="" \
    OC_URL=""
ENV PATH="/venv/bin:$PATH"

USER 1001
