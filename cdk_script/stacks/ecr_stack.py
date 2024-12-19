# Import required AWS CDK constructs
from aws_cdk import (
    Stack,               # Base stack class
    aws_ecr as ecr,      # Elastic Container Registry constructs
    RemovalPolicy,       # Resource removal policy
    Duration,            # Duration construct
)
from constructs import Construct
from ..config import (
    get_ecr_config, 
    get_project_name,
    get_cleanup_config,
    get_env_config  # Add this import
)

project_name = get_project_name()
env_name = get_env_config()

class ECRStack(Stack):
    """
    ECR Stack that creates and configures the Elastic Container Registry.
    This stack provides a repository for storing Docker images that will be used by ECS.
    """
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        # Initialize the parent Stack class
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from context
        config = get_ecr_config(scope, env_name)
        cleanup_config = get_cleanup_config(scope, env_name)

        # Create the ECR Repository with enhanced lifecycle rules
        self.repository = ecr.Repository(
            self,
            f"{env_name}-ECRRepository",
            repository_name=f"{config.repository_name}-{env_name}",
            removal_policy=RemovalPolicy.DESTROY,
            image_scan_on_push=config.enable_scan,
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            lifecycle_rules=[
                # Rule for tagged images
                ecr.LifecycleRule(
                    description="Keep only recent tagged images",
                    max_image_count=cleanup_config.ecr["maxTaggedImages"],
                    rule_priority=1,
                    selection_criteria=[ecr.TagStatus.TAGGED]
                ),
                # Rule for untagged images
                ecr.LifecycleRule(
                    description="Remove untagged images",
                    max_image_age=Duration.days(cleanup_config.ecr["untaggedRetentionDays"]),
                    rule_priority=2,
                    selection_criteria=[ecr.TagStatus.UNTAGGED]
                ),
                # Rule for specific tag prefixes
                ecr.LifecycleRule(
                    description="Clean up by tag prefixes",
                    max_image_count=cleanup_config.ecr["maxTaggedImages"],
                    rule_priority=3,
                    tag_prefix_list=cleanup_config.ecr["tagPrefixes"]
                )
            ],
            auto_delete_images=True
        )

    def create_repository(self):
        # Get cleanup configuration
        cleanup_config = get_cleanup_config(self, env_name)
        
        ecr.Repository(
            self,
            f"{project_name}-{env_name}-repo",
            repository_name=f"{project_name}-{env_name}",
            removal_policy=RemovalPolicy.DESTROY if env_name == "dev" else RemovalPolicy.RETAIN,
            lifecycle_rules=[
                # Rule for tagged images
                ecr.LifecycleRule(
                    description="Keep only recent tagged images",
                    max_image_count=cleanup_config.ecr["maxTaggedImages"],
                    rule_priority=1,
                    selection_criteria=[
                        ecr.TagStatus.TAGGED
                    ]
                ),
                # Rule for untagged images
                ecr.LifecycleRule(
                    description="Remove untagged images",
                    max_image_age=Duration.days(cleanup_config.ecr["untaggedRetentionDays"]),
                    rule_priority=2,
                    selection_criteria=[
                        ecr.TagStatus.UNTAGGED
                    ]
                ),
                # Rule for specific tag prefixes
                ecr.LifecycleRule(
                    description="Clean up by tag prefixes",
                    max_image_count=cleanup_config.ecr["maxTaggedImages"],
                    rule_priority=3,
                    tag_prefix_list=cleanup_config.ecr["tagPrefixes"]
                )
            ],
            image_scan_on_push=True
        )