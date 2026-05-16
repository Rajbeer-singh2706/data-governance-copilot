# Deploy Day 1 — AWS Setup, ECR, Dockerfile

## What this folder contains

| File | Purpose |
|---|---|
| `Dockerfile` | Copy to project root — builds the production Docker image |
| `.dockerignore` | Copy to project root — keeps secrets out of the image |
| `iam-policy.json` | Paste into IAM when creating copilot-deployer user |
| `deploy-day1-commands.sh` | All CLI commands in order — run section by section |

## Steps in order

### 1. AWS Account + IAM
1. Create AWS account at aws.amazon.com
2. Enable MFA on root account immediately
3. Set billing alarm: Billing → Budgets → $50/month
4. Create IAM user `copilot-deployer`
   - Attach the policy from `iam-policy.json`
   - Save Access Key ID + Secret Access Key
5. Run: `aws configure` with the deployer credentials
6. Verify: `aws sts get-caller-identity` shows copilot-deployer

### 2. ECR Repository
```bash
aws ecr create-repository \
  --repository-name data-governance-copilot \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true
```
Save the `repositoryUri` from the output.

### 3. Dockerfile
Copy `Dockerfile` and `.dockerignore` to your project root:
```
data-governance-copilot/
├── Dockerfile          ← here
├── .dockerignore       ← here
├── pyproject.toml
└── src/
```

### 4. Build and Test
```bash
# Build
docker build -t data-governance-copilot:latest .

# Test locally
docker run -p 8501:8501 -e ENABLE_MOCK=true data-governance-copilot:latest
# Open http://localhost:8501 — should see Streamlit app
```

### 5. Push to ECR
```bash
# Auth
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Tag
docker tag data-governance-copilot:latest \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/data-governance-copilot:latest

# Push
docker push \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/data-governance-copilot:latest
```

### 6. Verify
```bash
aws ecr describe-images \
  --repository-name data-governance-copilot \
  --region us-east-1
```
Should show `imageTags: ["latest"]` with a recent timestamp.

## Done ✅
Save this value for D-Day 3:
```
ECR_URI = ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/data-governance-copilot
```

## D-Day 2 Preview
VPC + subnets + security groups — the network that ECS will run inside.
