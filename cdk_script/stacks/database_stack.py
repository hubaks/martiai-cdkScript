from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_elasticache as elasticache,
    Duration,
    aws_sns as sns,
    RemovalPolicy,
    CfnTag,
)
from constructs import Construct
from ..config import get_database_config, get_project_name, get_alarm_config, get_cleanup_config
from ..utils.alarms import create_rds_alarms, create_redis_alarms

class DatabaseStack(Stack):
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        env_name: str, 
        vpc: ec2.Vpc, 
        app_security_group: ec2.SecurityGroup, 
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_name = get_project_name(scope)
        config = get_database_config(scope, env_name)
        alarm_config = get_alarm_config(scope, env_name)
        cleanup_config = get_cleanup_config(scope, env_name)  # Add this

        # Update RDS instance name
        rds_name = f"{project_name}-{env_name}-postgres-db"
        
        # Update Redis cluster name
        redis_name = f"{project_name}-{env_name}-redis-cluster"
        
        # Update security group names
        rds_sg_name = f"{project_name}-{env_name}-rds-sg"
        redis_sg_name = f"{project_name}-{env_name}-redis-sg"

        # Create Redis Security Group
        self.cache_security_group = ec2.SecurityGroup(
            self,
            redis_sg_name,
            vpc=vpc,
            description="Security Group for Redis Cluster",
            allow_all_outbound=True
        )

        # Create ElastiCache Subnet Group
        self.cache_subnet_group = elasticache.CfnSubnetGroup(
            self,
            f"{env_name}-Redis-SubnetGroup",
            subnet_ids=vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ).subnet_ids,
            description="Subnet Group for Redis Cluster"
        )

        # Create Redis Cluster
        self.redis_cluster = elasticache.CfnCacheCluster(
            self,
            redis_name,
            cache_node_type=config.redis.node_type,
            engine="redis",
            num_cache_nodes=config.redis.num_nodes,
            port=config.redis.port,
            vpc_security_group_ids=[self.cache_security_group.security_group_id],
            cache_subnet_group_name=self.cache_subnet_group.ref,
            cluster_name=redis_name,
            snapshot_retention_limit=cleanup_config.redis["snapshotRetentionDays"],
            snapshot_window=cleanup_config.redis["snapshotWindow"],
            preferred_maintenance_window=cleanup_config.redis["maintenanceWindow"],
            auto_minor_version_upgrade=True,
            tags=[
                CfnTag(
                    key="Environment",
                    value=env_name
                )
            ]
        )

        # Allow application to connect to Redis
        self.cache_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(app_security_group.security_group_id),
            connection=ec2.Port.tcp(config.redis.port),
            description="Allow application to connect to Redis"
        )

        # Create RDS Security Group
        self.rds_security_group = ec2.SecurityGroup(
            self,
            rds_sg_name,
            vpc=vpc,
            description="Security Group for RDS PostgreSQL",
            allow_all_outbound=True
        )

        # Create RDS Parameter Group
        self.db_parameter_group = rds.ParameterGroup(
            self,
            f"{env_name}-DBParameterGroup",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_14
            ),
            description="Custom parameter group for PostgreSQL 14"
        )

        # Create RDS Instance
        self.rds_instance = rds.DatabaseInstance(
            self,
            rds_name,
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_14
            ),
            instance_type=ec2.InstanceType(config.rds.instance_type),
            allocated_storage=config.rds.allocated_storage,
            max_allocated_storage=config.rds.max_allocated_storage,
            storage_type=rds.StorageType.GP2,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.rds_security_group],
            multi_az=config.rds.multi_az,
            backup_retention=Duration.days(cleanup_config.rds["backupRetentionDays"]),
            preferred_backup_window="03:00-04:00",
            preferred_maintenance_window=cleanup_config.rds["maintenanceWindow"],
            database_name=config.rds.database_name,
            port=config.rds.port,
            credentials=rds.Credentials.from_generated_secret(
                username="dbadmin",
                secret_name=f"{env_name}-db-credentials"
            ),
            parameter_group=self.db_parameter_group,
            deletion_protection=config.rds.deletion_protection,
            monitoring_interval=Duration.seconds(60),
            enable_performance_insights=True,
            performance_insights_retention=rds.PerformanceInsightRetention.DEFAULT,
            instance_identifier=rds_name,
            delete_automated_backups=cleanup_config.rds["deleteAutomatedBackups"],
            removal_policy=RemovalPolicy.SNAPSHOT if env_name == "prod" else RemovalPolicy.DESTROY,
            performance_insights_retention=rds.PerformanceInsightRetention.DEFAULT,
            allocated_storage=20,
            max_allocated_storage=100,
            storage_type=rds.StorageType.GP3
        )

        # Allow application to connect to PostgreSQL
        self.rds_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(app_security_group.security_group_id),
            connection=ec2.Port.tcp(config.rds.port),
            description="Allow application to connect to PostgreSQL"
        ) 

        # Get the alarm topic
        alarm_topic = sns.Topic.from_topic_arn(
            self,
            f"{project_name}-{env_name}-alarm-topic",
            f"arn:aws:sns:{self.region}:{self.account}:{project_name}-{env_name}-alarms"
        )

        # Create RDS alarms
        create_rds_alarms(
            self,
            project_name,
            env_name,
            alarm_config,
            self.rds_instance,
            alarm_topic
        )

        # Create Redis alarms
        create_redis_alarms(
            self,
            project_name,
            env_name,
            alarm_config,
            self.redis_cluster,
            alarm_topic
        ) 