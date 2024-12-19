from dataclasses import dataclass
from typing import Dict, Any
from constructs import Construct

@dataclass
class NetworkConfig:
    max_azs: int
    nat_gateways: int

@dataclass
class HealthCheckConfig:
    path: str
    interval: int
    timeout: int
    healthy_count: int
    unhealthy_count: int

@dataclass
class ScalingConfig:
    cpu_target_utilization: int
    requests_per_target: int
    scale_in_cooldown: int
    scale_out_cooldown: int

@dataclass
class ApplicationConfig:
    container_insights: bool
    task_cpu: int
    task_memory: int
    container_port: int
    desired_count: int
    min_tasks: int
    max_tasks: int
    health_check: HealthCheckConfig
    scaling: ScalingConfig
    database_name: str

@dataclass
class EcrConfig:
    repository_name: str
    max_image_count: int
    enable_scan: bool

@dataclass
class RedisConfig:
    node_type: str
    num_nodes: int
    port: int 

@dataclass
class RdsConfig:
    instance_type: str
    allocated_storage: int
    max_allocated_storage: int
    multi_az: bool
    backup_retention_days: int
    database_name: str
    port: int 
    deletion_protection: bool = False

@dataclass
class DatabaseConfig:
    redis: RedisConfig
    rds: RdsConfig

@dataclass
class AlarmConfig:
    costs: Dict[str, Any]
    rds: Dict[str, Any]
    redis: Dict[str, Any]
    ecs: Dict[str, Any]

@dataclass
class CleanupConfig:
    rds: Dict[str, Any]
    redis: Dict[str, Any]
    ecr: Dict[str, Any]

@dataclass
class PineconeConfig:
    api_key: str
    index_name: str

def get_cleanup_config(scope: Construct, env_name: str) -> CleanupConfig:
    config = get_env_config(scope, env_name)
    return CleanupConfig(**config["cleanup"])

def get_project_name(scope: Construct) -> str:
    """Get project name from context"""
    environments = scope.node.try_get_context("environments")
    if not environments or "projectName" not in environments:
        raise ValueError("Project name not found in context")
    return environments["projectName"]

def get_env_config(scope: Construct, env_name: str = "dev") -> Dict[str, Any]:
    """Get environment specific configuration from context"""
    environments = scope.node.try_get_context("environments")
    if not environments:
        raise ValueError("No environments configuration found in context")
    
    env_config = environments.get(env_name)
    if not env_config:
        raise ValueError(f"No configuration found for environment: {env_name}")
    
    return env_config

def get_network_config(scope: Construct, env_name: str) -> NetworkConfig:
    config = get_env_config(scope, env_name)
    return NetworkConfig(**config["network"])

def get_application_config(scope: Construct, env_name: str) -> ApplicationConfig:
    config = get_env_config(scope, env_name)
    app_config = config["application"]
    return ApplicationConfig(
        container_insights=app_config["containerInsights"],
        task_cpu=app_config["taskCpu"],
        task_memory=app_config["taskMemory"],
        container_port=app_config["containerPort"],
        desired_count=app_config["desiredCount"],
        min_tasks=app_config["minTasks"],
        max_tasks=app_config["maxTasks"],
        health_check=HealthCheckConfig(**app_config["healthCheck"]),
        scaling=ScalingConfig(**app_config["scaling"]),
        database_name=app_config["database"]["name"]
    )

def get_ecr_config(scope: Construct, env_name: str) -> EcrConfig:
    config = get_env_config(scope, env_name)
    return EcrConfig(**config["ecr"])

def get_database_config(scope: Construct, env_name: str) -> DatabaseConfig:
    config = get_env_config(scope, env_name)
    return DatabaseConfig(**config["database"]) 

def get_alarm_config(scope: Construct, env_name: str) -> AlarmConfig:
    config = get_env_config(scope, env_name)
    return AlarmConfig(**config["alarms"]) 

def get_pinecone_config(scope: Construct, env_name: str) -> PineconeConfig:
    config = get_env_config(scope, env_name)
    return PineconeConfig(**config["pinecone"]) 