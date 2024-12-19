# Import required AWS CDK constructs
from aws_cdk import (
    Stack,           # Base stack class
    aws_ec2 as ec2,  # EC2 and VPC constructs
    aws_sns as sns,  # SNS constructs
)
from constructs import Construct
from ..config import get_network_config, get_project_name, get_alarm_config
from ..utils.alarms import create_nat_gateway_alarms

class NetworkStack(Stack):
    """
    Network Stack that creates the VPC and related networking components.
    This stack provides the network foundation for all other stacks.
    """
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        # Initialize the parent Stack class
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from context
        config = get_network_config(scope, env_name)

        project_name = get_project_name(scope)
        alarm_config = get_alarm_config(scope, env_name)
        
        # Get the alarm topic
        alarm_topic = sns.Topic.from_topic_arn(
            self,
            f"{project_name}-{env_name}-alarm-topic",
            f"arn:aws:sns:{self.region}:{self.account}:{project_name}-{env_name}-alarms"
        )

        # Create a new VPC with the following configuration:
        # - Multiple Availability Zones for high availability
        # - Public and private subnets in each AZ
        # - NAT Gateway for private subnet internet access
        self.vpc = ec2.Vpc(
            self,  # Parent construct (this stack)
            f"{env_name}-VPC",  # Unique identifier for this VPC
            max_azs=config.max_azs,  # Use configured number of Availability Zones
            nat_gateways=config.nat_gateways  # Create configured number of NAT Gateways
            # Default subnet configuration:
            # - Public subnets (with Internet Gateway)
            # - Private subnets with NAT (for application components)
            # - Isolated private subnets (for databases)
        )

        # Create NAT Gateway alarms if you have NAT Gateways
        if self.vpc.nat_gateways > 0:
            create_nat_gateway_alarms(
                self,
                project_name,
                env_name,
                alarm_config,
                self.vpc,
                alarm_topic
            )