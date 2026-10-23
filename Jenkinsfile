pipeline {
    agent { label 'docker-terraform-aws' }

    parameters {
        string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'AWS region for ECR and EKS.')
        string(name: 'EKS_CLUSTER_NAME', defaultValue: 'capstone', description: 'EKS cluster managed by Terraform.')
        string(name: 'TF_STATE_BUCKET', defaultValue: '', description: 'Pre-created, versioned S3 bucket for Terraform state.')
        string(name: 'ANSIBLE_INVENTORY', defaultValue: 'ansible/inventory.ini', description: 'Path to the private Jenkins runner inventory.')
        string(name: 'NOTIFICATION_EMAIL', defaultValue: '', description: 'Optional recipient for Jenkins pipeline failures; requires email-ext and SMTP configuration.')
        booleanParam(name: 'RUN_INFRASTRUCTURE', defaultValue: false, description: 'Run Terraform plan and, after approval, apply infrastructure changes.')
        booleanParam(name: 'RUN_CONFIGURATION', defaultValue: false, description: 'Run Ansible against the configured Jenkins runner inventory.')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    environment {
        ECR_REPOSITORY = 'capstone-web'
        IMAGE_TAG = "${BUILD_NUMBER}"
        KUBE_NAMESPACE = 'capstone'
        PROMETHEUS_CHART_VERSION = '69.8.2'
        METRICS_SERVER_VERSION = 'v0.8.0'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Test') {
            steps {
                sh 'python3 -m compileall -q app tests'
                sh 'python3 -m unittest discover -s tests -v'
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build --pull -t "$ECR_REPOSITORY:$IMAGE_TAG" .'
            }
        }

        stage('Terraform plan') {
            when {
                allOf {
                    branch 'main'
                    expression { params.RUN_INFRASTRUCTURE == true }
                }
            }
            steps {
                dir('terraform') {
                    sh '''
                        terraform init -input=false \
                          -backend-config="bucket=$TF_STATE_BUCKET" \
                          -backend-config="key=capstone/terraform.tfstate" \
                          -backend-config="region=$AWS_REGION" \
                          -backend-config="use_lockfile=true"
                        terraform validate
                        terraform plan -input=false -out=tfplan \
                          -var="aws_region=$AWS_REGION" \
                                                    -var="cluster_name=$EKS_CLUSTER_NAME"
                    '''
                    stash name: 'terraform-plan', includes: 'tfplan'
                }
            }
        }

        stage('Approve infrastructure') {
            when {
                allOf {
                    branch 'main'
                    expression { params.RUN_INFRASTRUCTURE == true }
                }
            }
            steps {
                input message: 'Apply the reviewed Terraform plan? This can create billable AWS resources.', ok: 'Apply'
            }
        }

        stage('Terraform apply') {
            when {
                allOf {
                    branch 'main'
                    expression { params.RUN_INFRASTRUCTURE == true }
                }
            }
            steps {
                dir('terraform') {
                    unstash 'terraform-plan'
                    sh 'terraform init -input=false -backend-config="bucket=$TF_STATE_BUCKET" -backend-config="key=capstone/terraform.tfstate" -backend-config="region=$AWS_REGION" -backend-config="use_lockfile=true"'
                    sh 'terraform apply -input=false tfplan'
                }
            }
        }

        stage('Configure Jenkins runner') {
            when {
                allOf {
                    branch 'main'
                    expression { params.RUN_CONFIGURATION == true }
                }
            }
            steps {
                sh 'ansible-playbook --version'
                sh 'ansible-playbook -i "$ANSIBLE_INVENTORY" ansible/site.yml'
            }
        }

        stage('Push image') {
            when { branch 'main' }
            steps {
                sh '''
                    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
                    REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
                    aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" >/dev/null
                    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
                    docker tag "$ECR_REPOSITORY:$IMAGE_TAG" "$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"
                    docker push "$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"
                    echo "$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" > image-uri.txt
                '''
                stash name: 'image-uri', includes: 'image-uri.txt'
            }
        }

        stage('Deploy to EKS') {
            when { branch 'main' }
            steps {
                unstash 'image-uri'
                sh '''
                    IMAGE_URI=$(cat image-uri.txt)
                    aws eks update-kubeconfig --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION"
                    kubectl apply -f k8s/namespace.yaml
                    sed "s|replace-at-deploy/capstone-web:latest|$IMAGE_URI|" k8s/deployment.yaml | kubectl apply -n "$KUBE_NAMESPACE" -f -
                    kubectl apply -n "$KUBE_NAMESPACE" -f k8s/service.yaml
                    kubectl rollout status deployment/capstone-web -n "$KUBE_NAMESPACE" --timeout=180s
                '''
            }
        }

        stage('Smoke test') {
            when { branch 'main' }
            steps {
                sh '''
                    kubectl get deployment/capstone-web -n "$KUBE_NAMESPACE" -o jsonpath="{.status.availableReplicas}" | grep -E "^[1-9][0-9]*$"
                    kubectl exec deployment/capstone-web -n "$KUBE_NAMESPACE" -- python -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8080/healthz', timeout=3).status == 200"
                '''
            }
        }

        stage('Monitoring') {
            when { branch 'main' }
            steps {
                sh '''
                    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
                    kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/$METRICS_SERVER_VERSION/components.yaml"
                '''
                withCredentials([usernamePassword(credentialsId: 'monitoring-grafana', usernameVariable: 'GRAFANA_ADMIN_USER', passwordVariable: 'GRAFANA_ADMIN_PASSWORD')]) {
                    sh '''
                        kubectl create secret generic monitoring-grafana -n monitoring \\
                          --from-literal=admin-user="$GRAFANA_ADMIN_USER" \\
                          --from-literal=admin-password="$GRAFANA_ADMIN_PASSWORD" \\
                          --dry-run=client -o yaml | kubectl apply -f -
                    '''
                }
                sh '''
                    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
                    helm repo update
                    helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
                      --version "$PROMETHEUS_CHART_VERSION" \
                      --namespace monitoring \
                      --values monitoring/prometheus-values.yaml \
                      --wait --timeout 10m
                    kubectl apply -f k8s/autoscaling.yaml
                    kubectl apply -f k8s/servicemonitor.yaml
                    kubectl apply -f monitoring/alerts.yaml
                '''
            }
        }
    }

    post {
        always { deleteDir() }
        failure {
            echo 'Pipeline failed. Review the stage logs; Kubernetes rollout failures leave the prior ReplicaSet available for rollback.'
            script {
                if (params.NOTIFICATION_EMAIL?.trim()) {
                    emailext(
                        to: params.NOTIFICATION_EMAIL,
                        subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                        body: "Pipeline failed: ${env.BUILD_URL}"
                    )
                }
            }
        }
    }
}