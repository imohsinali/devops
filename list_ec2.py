import boto3

# Create an EC2 client. Boto3 has 'client' (low-level) and 'resource' (high-level) interfaces.
# We'll start with client.
ec2_client = boto3.client('ec2')

# Call the describe_instances API
response = ec2_client.describe_instances()

# The response is a giant, nested Python dictionary.
# Let's parse it to get useful information.
print("Instance ID\t\tState\t\tType")
print("----------------------------------------------")
for reservation in response['Reservations']:
    for instance in reservation['Instances']:
        instance_id = instance['InstanceId']
        state = instance['State']['Name']
        instance_type = instance['InstanceType']
        print(f"{instance_id}\t{state}\t\t{instance_type}")