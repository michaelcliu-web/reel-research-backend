#!/bin/bash
# AWS Infrastructure Setup Script for MyApp
# Prerequisites: aws configure must be completed with us-east-2 region
# Usage: bash deploy/aws-create-infra.sh

set -e

REGION="us-east-2"
KEY_NAME="myapp-key"
KEY_FILE="$HOME/Downloads/${KEY_NAME}.pem"
EC2_SG_NAME="myapp-ec2-sg"
RDS_SG_NAME="myapp-rds-sg"
DB_IDENTIFIER="myapp-db"
DB_NAME="myapp"
DB_USER="postgres"
INSTANCE_TYPE="t3.medium"
DB_INSTANCE_CLASS="db.t3.micro"

echo "=== MyApp AWS Infrastructure Setup ==="
echo "Region: $REGION"
echo ""

# Step 1: Get default VPC
echo "--- Finding default VPC ---"
VPC_ID=$(aws ec2 describe-vpcs --region $REGION --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)
echo "VPC ID: $VPC_ID"

# Step 2: Create Key Pair
echo ""
echo "--- Creating Key Pair ---"
if aws ec2 describe-key-pairs --region $REGION --key-names $KEY_NAME 2>/dev/null; then
    echo "Key pair '$KEY_NAME' already exists, skipping..."
else
    aws ec2 create-key-pair --region $REGION --key-name $KEY_NAME --query "KeyMaterial" --output text > "$KEY_FILE"
    chmod 400 "$KEY_FILE"
    echo "Key pair created and saved to $KEY_FILE"
fi

# Step 3: Create EC2 Security Group
echo ""
echo "--- Creating EC2 Security Group ---"
EC2_SG_ID=$(aws ec2 describe-security-groups --region $REGION --filters "Name=group-name,Values=$EC2_SG_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "None")

if [ "$EC2_SG_ID" = "None" ] || [ -z "$EC2_SG_ID" ]; then
    EC2_SG_ID=$(aws ec2 create-security-group --region $REGION --group-name $EC2_SG_NAME --description "MyApp EC2 security group" --vpc-id $VPC_ID --query "GroupId" --output text)
    echo "Created EC2 SG: $EC2_SG_ID"

    aws ec2 authorize-security-group-ingress --region $REGION --group-id $EC2_SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --region $REGION --group-id $EC2_SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --region $REGION --group-id $EC2_SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0
    echo "Ingress rules added (SSH, HTTP, HTTPS)"
else
    echo "EC2 SG already exists: $EC2_SG_ID"
fi

# Step 4: Create RDS Security Group
echo ""
echo "--- Creating RDS Security Group ---"
RDS_SG_ID=$(aws ec2 describe-security-groups --region $REGION --filters "Name=group-name,Values=$RDS_SG_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "None")

if [ "$RDS_SG_ID" = "None" ] || [ -z "$RDS_SG_ID" ]; then
    RDS_SG_ID=$(aws ec2 create-security-group --region $REGION --group-name $RDS_SG_NAME --description "MyApp RDS security group" --vpc-id $VPC_ID --query "GroupId" --output text)
    echo "Created RDS SG: $RDS_SG_ID"

    aws ec2 authorize-security-group-ingress --region $REGION --group-id $RDS_SG_ID --protocol tcp --port 5432 --source-group $EC2_SG_ID
    echo "Ingress rule added (PostgreSQL from EC2 SG only)"
else
    echo "RDS SG already exists: $RDS_SG_ID"
fi

# Step 5: Launch EC2 Instance
echo ""
echo "--- Launching EC2 Instance ---"
EXISTING_INSTANCE=$(aws ec2 describe-instances --region $REGION --filters "Name=tag:Name,Values=myapp-server" "Name=instance-state-name,Values=running,stopped" --query "Reservations[0].Instances[0].InstanceId" --output text 2>/dev/null || echo "None")

if [ "$EXISTING_INSTANCE" = "None" ] || [ -z "$EXISTING_INSTANCE" ]; then
    # Get latest Amazon Linux 2023 AMI
    AMI_ID=$(aws ec2 describe-images --region $REGION --owners amazon --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)
    echo "Using AMI: $AMI_ID"

    INSTANCE_ID=$(aws ec2 run-instances \
        --region $REGION \
        --image-id $AMI_ID \
        --instance-type $INSTANCE_TYPE \
        --key-name $KEY_NAME \
        --security-group-ids $EC2_SG_ID \
        --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]' \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=myapp-server}]" \
        --query "Instances[0].InstanceId" \
        --output text)
    echo "Launched EC2 instance: $INSTANCE_ID"
    echo "Waiting for instance to be running..."
    aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID
    echo "Instance is running!"
else
    INSTANCE_ID=$EXISTING_INSTANCE
    echo "EC2 instance already exists: $INSTANCE_ID"
fi

# Step 6: Allocate and Associate Elastic IP
echo ""
echo "--- Setting up Elastic IP ---"
EXISTING_EIP=$(aws ec2 describe-addresses --region $REGION --filters "Name=tag:Name,Values=myapp-eip" --query "Addresses[0].AllocationId" --output text 2>/dev/null || echo "None")

if [ "$EXISTING_EIP" = "None" ] || [ -z "$EXISTING_EIP" ]; then
    ALLOC_ID=$(aws ec2 allocate-address --region $REGION --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=myapp-eip}]" --query "AllocationId" --output text)
    ELASTIC_IP=$(aws ec2 describe-addresses --region $REGION --allocation-ids $ALLOC_ID --query "Addresses[0].PublicIp" --output text)
    aws ec2 associate-address --region $REGION --allocation-id $ALLOC_ID --instance-id $INSTANCE_ID
    echo "Elastic IP allocated and associated: $ELASTIC_IP"
else
    ELASTIC_IP=$(aws ec2 describe-addresses --region $REGION --allocation-ids $EXISTING_EIP --query "Addresses[0].PublicIp" --output text)
    echo "Elastic IP already exists: $ELASTIC_IP"
fi

# Step 7: Generate random DB password
DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

# Step 8: Create RDS Instance
echo ""
echo "--- Creating RDS PostgreSQL Instance ---"
EXISTING_DB=$(aws rds describe-db-instances --region $REGION --db-instance-identifier $DB_IDENTIFIER --query "DBInstances[0].DBInstanceIdentifier" --output text 2>/dev/null || echo "None")

if [ "$EXISTING_DB" = "None" ] || [ -z "$EXISTING_DB" ]; then
    aws rds create-db-instance \
        --region $REGION \
        --db-instance-identifier $DB_IDENTIFIER \
        --db-instance-class $DB_INSTANCE_CLASS \
        --engine postgres \
        --engine-version "15" \
        --master-username $DB_USER \
        --master-user-password "$DB_PASSWORD" \
        --db-name $DB_NAME \
        --allocated-storage 20 \
        --storage-type gp3 \
        --vpc-security-group-ids $RDS_SG_ID \
        --no-publicly-accessible \
        --backup-retention-period 7 \
        --tags Key=Name,Value=myapp-db

    echo "RDS instance creation initiated (takes 5-10 minutes)..."
    echo "Waiting for RDS to become available..."
    aws rds wait db-instance-available --region $REGION --db-instance-identifier $DB_IDENTIFIER
    echo "RDS is available!"

    RDS_ENDPOINT=$(aws rds describe-db-instances --region $REGION --db-instance-identifier $DB_IDENTIFIER --query "DBInstances[0].Endpoint.Address" --output text)
else
    echo "RDS instance already exists"
    RDS_ENDPOINT=$(aws rds describe-db-instances --region $REGION --db-instance-identifier $DB_IDENTIFIER --query "DBInstances[0].Endpoint.Address" --output text)
    DB_PASSWORD="<existing-password-check-your-records>"
fi

echo ""
echo "============================================"
echo "=== AWS Infrastructure Setup Complete! ==="
echo "============================================"
echo ""
echo "EC2 Instance ID:  $INSTANCE_ID"
echo "Elastic IP:       $ELASTIC_IP"
echo "EC2 Security Group: $EC2_SG_ID"
echo "RDS Endpoint:     $RDS_ENDPOINT"
echo "RDS Security Group: $RDS_SG_ID"
echo "DB Password:      $DB_PASSWORD"
echo "Key File:         $KEY_FILE"
echo ""
echo "Next steps:"
echo "  1. Configure DNS: A record for api.example.com -> $ELASTIC_IP"
echo "  2. SSH: ssh -i $KEY_FILE ec2-user@$ELASTIC_IP"
echo "  3. Run ec2-setup.sh on the instance"
echo "  4. Clone repo, create .env.prod, deploy"
echo ""

# Save outputs for later use
cat > /tmp/myapp-infra-output.env <<EOF
ELASTIC_IP=$ELASTIC_IP
INSTANCE_ID=$INSTANCE_ID
EC2_SG_ID=$EC2_SG_ID
RDS_ENDPOINT=$RDS_ENDPOINT
RDS_SG_ID=$RDS_SG_ID
DB_PASSWORD=$DB_PASSWORD
KEY_FILE=$KEY_FILE
EOF

echo "Infrastructure details saved to /tmp/myapp-infra-output.env"
