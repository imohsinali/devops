import boto3
import os
from botocore.exceptions import ClientError
#  aws ec2 create-key-pair --key-name windows-python-key --query 'KeyMaterial' --output text > windows-python-key.pem
# this commad will create windows-python-key.pem in your current directory
# Create EC2 client and resource
ec2_client = boto3.client('ec2')
ec2_resource = boto3.resource('ec2')

def get_free_tier_instance_type():
    """
    Returns a free-tier eligible instance type dynamically
    """
    try:
        response = ec2_client.describe_instance_types(
            Filters=[
                {
                    'Name': 'free-tier-eligible',
                    'Values': ['true']
                }
            ],
            MaxResults=5
        )
        
        if response['InstanceTypes']:
            # Return the first available free tier instance type
            instance_type = response['InstanceTypes'][0]['InstanceType']
            print(f"Found free-tier instance type: {instance_type}")
            return instance_type
        else:
            print("No free-tier instance types found, using t2.micro as fallback")
            return 't3.micro'
            
    except ClientError as e:
        print(f"Error querying instance types: {e}, using t2.micro as fallback")
        return 't3.micro'

def check_key_pair(key_name):
    """
    Check if the key pair exists and if the .pem file is available
    """
    try:
        # Check if key pair exists in AWS
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"Key pair '{key_name}' found in AWS.")
        
        # Check if .pem file exists locally
        pem_file = f"{key_name}.pem"
        if os.path.exists(pem_file):
            print(f"Private key file '{pem_file}' found locally.")
        else:
            print(f"⚠ Warning: Private key file '{pem_file}' not found in current directory.")
            print("  You will need this file to connect to your instance via SSH.")
            
        return True
        
    except ClientError as e:
        if 'InvalidKeyPair.NotFound' in str(e):
            print(f"❌ ERROR: Key pair '{key_name}' does not exist in AWS!")
            print(f"\nPlease create it first with:")
            print(f"aws ec2 create-key-pair --key-name {key_name} --query 'KeyMaterial' --output text > {key_name}.pem")
            print(f"\nThis will create {key_name}.pem in your current directory")
            return False
        else:
            print(f"Error checking key pair: {e}")
            return False

def create_security_group():
    group_name = 'python-sg-for-ssh'
    description = 'Security group for EC2 instance created via Python'
    
    try:
        # Check if the security group already exists
        response = ec2_client.describe_security_groups(
            GroupNames=[group_name]
        )
        print(f"Security group '{group_name}' already exists. Using it.")
        return response['SecurityGroups'][0]['GroupId']
        
    except ClientError as e:
        # If it doesn't exist, create it
        if 'InvalidGroup.NotFound' in str(e):
            print(f"Creating new security group: '{group_name}'")
            try:
                response = ec2_client.create_security_group(
                    GroupName=group_name,
                    Description=description,
                )
                security_group_id = response['GroupId']
                print(f"Security Group Created: {security_group_id}")
                
                # Add SSH access rule (port 22)
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group_id,
                    IpPermissions=[
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': 22,
                            'ToPort': 22,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}] # WARNING: Allows SSH from ANYWHERE. For learning only!
                        }
                    ]
                )
                print("SSH rule added (Port 22 open to world).")
                return security_group_id
            except ClientError as sg_error:
                print(f"Error creating security group: {sg_error}")
                return None
        else:
            print(f"Error checking for security group: {e}")
            return None

def print_windows_connection_instructions(key_name, public_ip):
    """
    Print Windows-specific connection instructions
    """
    if not public_ip:
        return
        
    print("\n" + "="*60)
    print("WINDOWS CONNECTION INSTRUCTIONS")
    print("="*60)
    
    print(f"\nPublic IP: {public_ip}")
    print(f"Username: ec2-user")
    print(f"Key file: {key_name}.pem")
    
    print("\nOption 1: Using MobaXterm (Recommended for Windows)")
    print("  1. Download MobaXterm: https://mobaxterm.mobatek.net/")
    print("  2. Session -> SSH -> Enter the IP above")
    print("  3. Specify username: ec2-user")
    print(f"  4. Advanced SSH settings -> Use private key: {key_name}.pem")
    
    print("\nOption 2: Using PuTTY")
    print("  1. Convert .pem to .ppk using PuTTYgen")
    print("  2. Use PuTTY with the .ppk file")
    print(f"  3. Host: ec2-user@{public_ip}")
    
    print("\nOption 3: Using AWS Session Manager (No SSH client needed)")
    print(f"  1. aws ssm start-session --target your-instance-id")

def main():
    print("="*60)
    print("EC2 Instance Creator with Free-Tier Detection")
    print("="*60)
    
    # Your Key Pair name - YOU MUST CHANGE THIS!
    key_name = 'my-python-key'  # <<< CHANGE THIS TO YOUR KEY NAME!
    
    # Check if key pair exists
    if not check_key_pair(key_name):
        print("Failed due to missing key pair. Exiting.")
        return

    # Get free-tier instance type dynamically
    instance_type = get_free_tier_instance_type()
    
    # Get the security group ID
    sg_id = create_security_group()
    if not sg_id:
        print("Failed to get a security group. Exiting.")
        return

    # AMI ID (Amazon Linux 2 in us-east-1)
    ami_id = 'ami-0c02fb55956c7d316'

    try:
        # Launch the instance
        instances = ec2_resource.create_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,  # Using dynamic instance type
            KeyName=key_name,
            SecurityGroupIds=[sg_id],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': 'MyPythonInstance'}]
            }]
        )
        
        instance = instances[0]
        print("\n" + "="*50)
        print("SUCCESS: EC2 Instance Launched!")
        print("="*50)
        print(f"Instance ID: {instance.id}")
        print(f"Instance Type: {instance_type}")
        print(f"Key Pair: {key_name}")
        print(f"Security Group: {sg_id}")
        
        # Wait for instance to be running and get public IP
        print("\nWaiting for instance to initialize...")
        instance.wait_until_running()
        instance.load()  # Refresh instance data
        
        print(f"Instance State: {instance.state['Name']}")
        if instance.public_ip_address:
            print(f"Public IP: {instance.public_ip_address}")
            
            # Print Windows connection instructions
            print_windows_connection_instructions(key_name, instance.public_ip_address)
            
            # Save connection info to file
            with open('instance_connection.txt', 'w') as f:
                f.write(f"Instance ID: {instance.id}\n")
                f.write(f"Public IP: {instance.public_ip_address}\n")
                f.write(f"Key Pair: {key_name}.pem\n")
                f.write(f"Connect: ec2-user@{instance.public_ip_address}\n")
            print(f"\nConnection info saved to 'instance_connection.txt'")
        
        print(f"\nUse this command to check status:")
        print(f"aws ec2 describe-instances --instance-ids {instance.id}")
        
    except ClientError as e:
        print(f"Failed to launch instance: {e}")
        # Common errors: Invalid AMI, Invalid Key Pair, insufficient permissions

if __name__ == '__main__':
    main()