from aws_cdk import (
    Stack,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_ecs_patterns as ecs_patterns,
    Duration,
    CfnOutput,
    aws_sns as sns,
)
from constructs import Construct
from ..utils.alarms import create_ecs_alarms
from ..config import get_project_name, get_alarm_config,get_application_config

class ApplicationStack(Stack):
    """
    Application Stack that creates the ECS/Fargate service and related components.
    This stack provides the container runtime environment for the application.
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        env_name: str,
        vpc: ec2.Vpc,
        ecr_repository,
        **kwargs
    ) -> None:
        # Initialize the parent Stack class
        super().__init__(scope, construct_id, **kwargs)

        # Get configuration from context
        config = get_application_config(scope, env_name)
        project_name = get_project_name(scope)
        alarm_config = get_alarm_config(scope, env_name)
        
        # Get the alarm topic
        alarm_topic = sns.Topic.from_topic_arn(
            self,
            f"{project_name}-{env_name}-alarm-topic",
            f"arn:aws:sns:{self.region}:{self.account}:{project_name}-{env_name}-alarms"
        )

        # Create ECS Cluster
        self.cluster = ecs.Cluster(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-Cluster",  # Unique identifier for this cluster
            vpc=vpc,  # VPC to place the cluster in
            cluster_name=f"{project_name}-{env_name}-cluster",  # Physical cluster name
            container_insights=config.container_insights  # Enable/disable Container Insights
        )

        # Create Fargate Task Definition
        self.task_definition = ecs.FargateTaskDefinition(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-TaskDef",  # Unique identifier for this task definition
            memory_limit_mib=config.task_memory,  # Task memory limit
            cpu=config.task_cpu,  # Task CPU units
        )

        # Add Container to Task Definition
        self.container = self.task_definition.add_container(
            f"{project_name}-{env_name}-Container",  # Container name
            image=ecs.ContainerImage.from_registry("nginx:latest"),  # Use nginx as placeholder
            memory_limit_mib=config.task_memory,  # Container memory limit
            cpu=config.task_cpu,  # Container CPU units
            environment={
                "ENV": env_name,  # Environment name
                "DB_NAME": config.database_name  # Database name
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=f"{project_name}-{env_name}-container"  # CloudWatch logs prefix
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost/ || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3
            )
        )

        # Add Port Mapping
        self.container.add_port_mappings(
            ecs.PortMapping(
                container_port=config.container_port,  # Port the container listens on
                protocol=ecs.Protocol.TCP  # Protocol to use
            )
        )

        # Create Fargate Service with Load Balancer
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,  # Parent construct (this stack)
            f"{project_name}-{env_name}-Service",  # Unique identifier for this service
            cluster=self.cluster,  # ECS cluster to run in
            task_definition=self.task_definition,  # Task definition to use
            desired_count=config.desired_count,  # Number of tasks to run
            service_name=f"{project_name}-{env_name}-service",  # Physical service name
            public_load_balancer=True,  # Internet-facing load balancer
            listener_port=config.container_port,  # Port the load balancer listens on
            assign_public_ip=False,  # Use private IPs for tasks
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS  # Use private subnets
            )
        )

        # Configure health checks
        self.fargate_service.target_group.configure_health_check(
            path=config.health_check.path,  # Health check endpoint
            healthy_http_codes="200",  # Expected response code
            interval=Duration.seconds(config.health_check.interval),  # Check interval
            timeout=Duration.seconds(config.health_check.timeout),  # Check timeout
            healthy_threshold_count=config.health_check.healthy_count,  # Success threshold
            unhealthy_threshold_count=config.health_check.unhealthy_count  # Failure threshold
        )

        # Configure security for the load balancer
        self.fargate_service.load_balancer.connections.allow_from_any_ipv4(
            ec2.Port.tcp(config.container_port),  # Allow inbound traffic on container port
            description="Allow inbound HTTP traffic"
        )

        # Configure auto scaling
        scaling = self.fargate_service.service.auto_scale_task_count(
            min_capacity=config.min_tasks,  # Minimum number of tasks
            max_capacity=config.max_tasks  # Maximum number of tasks
        )

        # Scale based on CPU utilization
        scaling.scale_on_cpu_utilization(
            "CpuScaling",  # Unique identifier for this scaling rule
            target_utilization_percent=config.scaling.cpu_target_utilization,  # CPU utilization target
            scale_in_cooldown=Duration.seconds(config.scaling.scale_in_cooldown),  # Scale in cooldown
            scale_out_cooldown=Duration.seconds(config.scaling.scale_out_cooldown)  # Scale out cooldown
        )

        # Scale based on request count
        scaling.scale_on_request_count(
            "RequestCountScaling",  # Unique identifier for this scaling rule
            requests_per_target=config.scaling.requests_per_target,  # Request count target
            target_group=self.fargate_service.target_group  # Target group to monitor
        )

        # Create ECS alarms
        create_ecs_alarms(
            self,
            project_name,
            env_name,
            alarm_config,
            self.fargate_service,
            alarm_topic
        )

        # Outputs
        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self.fargate_service.load_balancer.load_balancer_dns_name,
            description="Load Balancer DNS Name"
        )

        CfnOutput(
            self,
            "ServiceURL",
            value=f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}",
            description="Service URL"
        )

    def add_database_config(self, rds_instance, redis_endpoint: str, redis_port: str):
        """Method to update container with database configuration after database stack is created"""
        # Add RDS configuration
        self.container.add_environment("DB_HOST", rds_instance.instance_endpoint.hostname)
        self.container.add_environment("DB_PORT", str(rds_instance.instance_endpoint.port))
        self.container.add_secret(
            "DB_CREDENTIALS",
            ecs.Secret.from_secrets_manager(rds_instance.secret)
        )

        # Add Redis configuration
        self.container.add_environment("REDIS_ENDPOINT", redis_endpoint)
        self.container.add_environment("REDIS_PORT", redis_port) 