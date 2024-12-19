# Import required AWS CDK core constructs
from aws_cdk import Stack, CfnOutput
# Import the base Construct class
from constructs import Construct
# Import our custom stack modules
from .stacks.network_stack import NetworkStack      # VPC and networking components
from .stacks.ecr_stack import ECRStack             # Container registry components
from .stacks.database_stack import DatabaseStack    # RDS and Redis components
from .stacks.application_stack import ApplicationStack  # ECS/Fargate components
from .stacks.WebsiteScrapingStack import WebsiteScrappingStack
from .utils.alarms import create_alarm_topic, create_cost_alarms
from .config import get_project_name, get_alarm_config  # Configuration utilities
from .stacks.FileUploadStack import FileUploadStack
class CdkScriptStack(Stack):
    """
    Main CDK Stack that orchestrates all sub-stacks and their dependencies.
    This stack is responsible for creating and connecting all infrastructure components.
    """
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        # Initialize the parent Stack class
        super().__init__(scope, construct_id, **kwargs)

        # Retrieve deployment environment configuration from CDK context
        # These values can be overridden during deployment using cdk.json or --context flag
        env_name = self.node.try_get_context("env_name") or "dev"  # Environment name (dev/staging/prod)
        aws_region = self.node.try_get_context("aws_region") or "us-east-1"  # AWS region to deploy to

        project_name = get_project_name(self)
        alarm_config = get_alarm_config(self, env_name)

        # Create SNS topic for alarms
        alarm_topic = create_alarm_topic(self, project_name, env_name)
        
        # Create cost alarms
        create_cost_alarms(self, project_name, env_name, alarm_config, alarm_topic)

        # Step 1: Create the Network Stack
        # This must be created first as all other stacks depend on the VPC
        network_stack = NetworkStack(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-NetworkStack",  # Unique identifier for this stack
            env_name=env_name  # Pass environment name for resource naming
        )

        # Step 2: Create the ECR Stack
        # This creates the container registry for storing Docker images
        ecr_stack = ECRStack(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-ECRStack",  # Unique identifier for this stack
            env_name=env_name  # Pass environment name for resource naming
        )

        # Step 3: Create the Application Stack
        # We create this before the database stack because we need its security group
        # for the database stack's security group rules
        app_stack = ApplicationStack(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-AppStack",  # Unique identifier for this stack
            env_name=env_name,  # Pass environment name for resource naming
            vpc=network_stack.vpc,  # Pass VPC from network stack
            ecr_repository=ecr_stack.repository  # Pass ECR repository from ECR stack
        )

        # Step 4: Create the Database Stack
        # This creates both RDS and Redis instances with proper security group rules
        database_stack = DatabaseStack(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-DatabaseStack",  # Unique identifier for this stack
            env_name=env_name,  # Pass environment name for resource naming
            vpc=network_stack.vpc,  # Pass VPC from network stack
            # Pass the application's security group for creating ingress rules
            app_security_group=app_stack.fargate_service.service.connections.security_groups[0]
        )

        # Step 5: Configure the Application Stack with Database Information
        # Now that both database and application stacks exist, we can connect them
        app_stack.add_database_config(
            rds_instance=database_stack.rds_instance,  # Pass RDS instance for connection info
            redis_endpoint=database_stack.redis_cluster.attr_redis_endpoint_address,  # Redis host
            redis_port=database_stack.redis_cluster.attr_redis_endpoint_port  # Redis port
        )

        web_scrapping_stack = WebsiteScrappingStack(self,
                                            f"{project_name}-{env_name}-WebsiteScrappingStack", 
                                            marti_vpc = network_stack.vpc, 
                                            database_stack = database_stack, 
                                            env=env_name)

        file_upload_stack = FileUploadStack(self,
                                            f"{project_name}-{env_name}-FileUploadStack", 
                                            marti_vpc = network_stack.vpc, 
                                            database_stack = database_stack, 
                                            env=env_name)

        # Step 6: Create CloudFormation Outputs
        # These values will be displayed after stack deployment
        
        # Output the ECR repository URI for pushing Docker images
        CfnOutput(
            self,
            "ECRRepositoryURI",
            value=ecr_stack.repository.repository_uri,
            description="ECR Repository URI"
        )

        # Output the Redis endpoint for application configuration
        CfnOutput(
            self,
            "RedisEndpoint",
            value=database_stack.redis_cluster.attr_redis_endpoint_address,
            description="Redis Cluster Endpoint"
        )

        # Output the RDS endpoint for application configuration
        CfnOutput(
            self,
            "RDSEndpoint",
            value=database_stack.rds_instance.instance_endpoint.hostname,
            description="RDS Instance Endpoint"
        )
        
        CfnOutput(
            self,
            "WebsiteScrapingStack",
            value=web_scrapping_stack.create_job_lambda.function_name,
            description="Website Scraping Stack"
        )

        CfnOutput(
            self,
            "FileUploadStack",
            value=file_upload_stack.pdf_function.function_name,
            description="File Upload Stack"
        )