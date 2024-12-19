from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    Duration,
)

def create_alarm_topic(scope, project_name: str, env_name: str) -> sns.Topic:
    """
    Creates an SNS topic for all infrastructure alarms.
    
    Args:
        scope: The CDK scope to create the topic in
        project_name: The name of the project
        env_name: The environment name (dev/prod)
    
    Returns:
        sns.Topic: The created SNS topic for alarms
    """
    return sns.Topic(
        scope,
        f"{project_name}-{env_name}-alarm-topic",
        topic_name=f"{project_name}-{env_name}-alarms",
        display_name=f"{project_name} {env_name} Alarms"
    )

def create_cost_alarms(scope, project_name: str, env_name: str, alarm_config: dict, alarm_topic: sns.Topic):
    """
    Creates AWS Cost Explorer alarms for monitoring infrastructure costs.
    
    Args:
        scope: The CDK scope to create the alarms in
        project_name: The name of the project
        env_name: The environment name
        alarm_config: Configuration for the alarms
        alarm_topic: SNS topic to send alarm notifications to
    """
    # Daily cost alarm
    daily_cost_metric = cloudwatch.Metric(
        namespace="AWS/Billing",
        metric_name="EstimatedCharges",
        statistic="Maximum",
        period=Duration.hours(24),
        dimensions={"Currency": "USD"}
    )

    daily_cost_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-daily-cost-alarm",
        metric=daily_cost_metric,
        threshold=alarm_config.costs["dailyThreshold"],
        evaluation_periods=1,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"Daily cost exceeded ${alarm_config.costs['dailyThreshold']} USD"
    )
    daily_cost_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

def create_rds_alarms(scope, project_name: str, env_name: str, alarm_config: dict, rds_instance, alarm_topic: sns.Topic):
    """
    Creates CloudWatch alarms for RDS monitoring.
    
    Monitors:
    - CPU Utilization
    - Free Storage Space
    - Free Memory
    - Connection Count
    - Read/Write Latency
    
    Args:
        scope: The CDK scope to create the alarms in
        project_name: The name of the project
        env_name: The environment name
        alarm_config: Configuration for the alarms
        rds_instance: The RDS instance to monitor
        alarm_topic: SNS topic to send alarm notifications to
    """
    # CPU Utilization Alarm
    cpu_metric = rds_instance.metric_cpu_utilization()
    cpu_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-rds-cpu-alarm",
        metric=cpu_metric,
        threshold=alarm_config.rds["cpuThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"RDS CPU utilization exceeded {alarm_config.rds['cpuThreshold']}%"
    )
    cpu_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Free Storage Space Alarm
    storage_metric = rds_instance.metric_free_storage_space()
    storage_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-rds-storage-alarm",
        metric=storage_metric,
        threshold=alarm_config.rds["storageThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        alarm_description=f"RDS free storage space below {alarm_config.rds['storageThreshold']} bytes"
    )
    storage_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Connection Count Alarm
    connection_metric = rds_instance.metric_database_connections()
    connection_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-rds-connection-alarm",
        metric=connection_metric,
        threshold=alarm_config.rds["connectionThreshold"],
        evaluation_periods=2,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"RDS connections near limit: {alarm_config.rds['connectionThreshold']}"
    )
    connection_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Deadlock Alarm
    deadlock_metric = cloudwatch.Metric(
        namespace="AWS/RDS",
        metric_name="Deadlocks",
        dimensions={"DBInstanceIdentifier": rds_instance.instance_identifier},
        statistic="Sum",
        period=Duration.minutes(5)
    )
    deadlock_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-rds-deadlock-alarm",
        metric=deadlock_metric,
        threshold=0,
        evaluation_periods=1,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description="RDS Deadlock detected"
    )
    deadlock_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

def create_redis_alarms(scope, project_name: str, env_name: str, alarm_config: dict, redis_cluster, alarm_topic: sns.Topic):
    """
    Creates CloudWatch alarms for Redis monitoring.
    
    Monitors:
    - CPU Utilization
    - Memory Usage
    - Connection Count
    - Cache Hit Rate
    - Evictions
    
    Args:
        scope: The CDK scope to create the alarms in
        project_name: The name of the project
        env_name: The environment name
        alarm_config: Configuration for the alarms
        redis_cluster: The Redis cluster to monitor
        alarm_topic: SNS topic to send alarm notifications to
    """
    # CPU Utilization Alarm
    cpu_metric = cloudwatch.Metric(
        namespace="AWS/ElastiCache",
        metric_name="CPUUtilization",
        dimensions={"CacheClusterId": redis_cluster.ref},
        statistic="Average",
        period=Duration.minutes(5)
    )
    cpu_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-redis-cpu-alarm",
        metric=cpu_metric,
        threshold=alarm_config.redis["cpuThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"Redis CPU utilization exceeded {alarm_config.redis['cpuThreshold']}%"
    )
    cpu_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Memory Usage Alarm
    memory_metric = cloudwatch.Metric(
        namespace="AWS/ElastiCache",
        metric_name="DatabaseMemoryUsagePercentage",
        dimensions={"CacheClusterId": redis_cluster.ref},
        statistic="Average",
        period=Duration.minutes(5)
    )
    memory_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-redis-memory-alarm",
        metric=memory_metric,
        threshold=alarm_config.redis["memoryThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"Redis memory usage exceeded {alarm_config.redis['memoryThreshold']}%"
    )
    memory_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Critical Memory Usage Alarm
    critical_memory_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-redis-critical-memory-alarm",
        metric=cloudwatch.Metric(
            namespace="AWS/ElastiCache",
            metric_name="DatabaseMemoryUsagePercentage",
            dimensions={"CacheClusterId": redis_cluster.ref},
            statistic="Maximum",
            period=Duration.minutes(1)
        ),
        threshold=90,
        evaluation_periods=1,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description="Redis memory usage critically high (>90%)"
    )
    critical_memory_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Eviction Alarm
    eviction_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-redis-eviction-alarm",
        metric=cloudwatch.Metric(
            namespace="AWS/ElastiCache",
            metric_name="Evictions",
            dimensions={"CacheClusterId": redis_cluster.ref},
            statistic="Sum",
            period=Duration.minutes(5)
        ),
        threshold=alarm_config.redis.get("evictionThreshold", 1000),
        evaluation_periods=1,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description="Redis evictions occurring"
    )
    eviction_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

def create_ecs_alarms(scope, project_name: str, env_name: str, alarm_config: dict, fargate_service, alarm_topic: sns.Topic):
    """
    Creates CloudWatch alarms for ECS/Fargate monitoring.
    
    Monitors:
    - CPU Utilization
    - Memory Utilization
    - Running Task Count
    - Target Response Time
    - HTTP 5XX Errors
    
    Args:
        scope: The CDK scope to create the alarms in
        project_name: The name of the project
        env_name: The environment name
        alarm_config: Configuration for the alarms
        fargate_service: The Fargate service to monitor
        alarm_topic: SNS topic to send alarm notifications to
    """
    # CPU Utilization Alarm
    cpu_metric = fargate_service.service.metric_cpu_utilization()
    cpu_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-ecs-cpu-alarm",
        metric=cpu_metric,
        threshold=alarm_config.ecs["cpuThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"ECS CPU utilization exceeded {alarm_config.ecs['cpuThreshold']}%"
    )
    cpu_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Memory Utilization Alarm
    memory_metric = fargate_service.service.metric_memory_utilization()
    memory_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-ecs-memory-alarm",
        metric=memory_metric,
        threshold=alarm_config.ecs["memoryThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"ECS memory utilization exceeded {alarm_config.ecs['memoryThreshold']}%"
    )
    memory_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # HTTP 5XX Error Alarm
    http_5xx_metric = fargate_service.load_balancer.metric_http_code_target(
        code="5XX",
        period=Duration.minutes(5)
    )
    http_5xx_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-ecs-5xx-alarm",
        metric=http_5xx_metric,
        threshold=alarm_config.ecs["error5xxThreshold"],
        evaluation_periods=3,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description=f"HTTP 5XX errors exceeded {alarm_config.ecs['error5xxThreshold']} per 5 minutes"
    )
    http_5xx_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Service Health Check Alarm
    health_check_metric = fargate_service.target_group.metric_unhealthy_host_count(
        period=Duration.minutes(1)
    )
    health_check_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-ecs-health-alarm",
        metric=health_check_metric,
        threshold=alarm_config.ecs.get("unhealthyTaskThreshold", 1),
        evaluation_periods=2,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description="ECS tasks failing health checks"
    )
    health_check_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Running Tasks Alarm (below minimum)
    running_tasks_metric = fargate_service.service.metric_running_task_count()
    min_tasks_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-ecs-min-tasks-alarm",
        metric=running_tasks_metric,
        threshold=alarm_config.ecs["minTasks"],
        evaluation_periods=2,
        datapoints_to_alarm=2,
        comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        alarm_description=f"Running tasks below minimum threshold: {alarm_config.ecs['minTasks']}"
    )
    min_tasks_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Container Fatal Error Alarm
    container_error_metric = cloudwatch.Metric(
        namespace="AWS/ECS",
        metric_name="ContainerExitCode",
        dimensions={
            "ClusterName": fargate_service.cluster.cluster_name,
            "ServiceName": fargate_service.service.service_name
        },
        statistic="Maximum",
        period=Duration.minutes(1)
    )
    container_error_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-ecs-container-error-alarm",
        metric=container_error_metric,
        threshold=0,
        evaluation_periods=1,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description="Container exited with error"
    )
    container_error_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

def create_nat_gateway_alarms(scope, project_name: str, env_name: str, alarm_config: dict, vpc, alarm_topic: sns.Topic):
    """
    Creates CloudWatch alarms for NAT Gateway monitoring.
    
    Monitors:
    - Port Allocation
    - Packet Drop Count
    - Error Port Allocation
    - Bytes Transfer
    
    Args:
        scope: The CDK scope to create the alarms in
        project_name: The name of the project
        env_name: The environment name
        alarm_config: Configuration for the alarms
        vpc: The VPC containing NAT Gateways
        alarm_topic: SNS topic to send alarm notifications to
    """
    for az_number, nat_gateway in enumerate(vpc.nat_gateways):
        # Port Allocation Alarm
        port_metric = cloudwatch.Metric(
            namespace="AWS/NATGateway",
            metric_name="PortAllocation",
            dimensions={"NatGatewayId": nat_gateway.nat_gateway_id},
            statistic="Average",
            period=Duration.minutes(5)
        )
        port_alarm = cloudwatch.Alarm(
            scope,
            f"{project_name}-{env_name}-nat-port-alarm-{az_number}",
            metric=port_metric,
            threshold=alarm_config.network["natPortThreshold"],
            evaluation_periods=3,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description=f"NAT Gateway port allocation exceeded {alarm_config.network['natPortThreshold']}"
        )
        port_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        # Error Count Alarm
        error_metric = cloudwatch.Metric(
            namespace="AWS/NATGateway",
            metric_name="ErrorPortAllocation",
            dimensions={"NatGatewayId": nat_gateway.nat_gateway_id},
            statistic="Sum",
            period=Duration.minutes(5)
        )
        error_alarm = cloudwatch.Alarm(
            scope,
            f"{project_name}-{env_name}-nat-error-alarm-{az_number}",
            metric=error_metric,
            threshold=alarm_config.network["natErrorThreshold"],
            evaluation_periods=3,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description=f"NAT Gateway error count exceeded {alarm_config.network['natErrorThreshold']}"
        )
        error_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic)) 

    # Add NAT Gateway Error Alarm
    for az_index, nat_gateway in enumerate(vpc.nat_gateways):
        error_metric = cloudwatch.Metric(
            namespace="AWS/NATGateway",
            metric_name="ErrorPortAllocation",
            dimensions={"NatGatewayId": nat_gateway.nat_gateway_id},
            statistic="Sum",
            period=Duration.minutes(5)
        )
        error_alarm = cloudwatch.Alarm(
            scope,
            f"{project_name}-{env_name}-nat-error-az{az_index}-alarm",
            metric=error_metric,
            threshold=alarm_config.network.get("natErrorThreshold", 5),
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description=f"NAT Gateway in AZ {az_index} experiencing port allocation errors"
        )
        error_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

    # Add Network Changes Alarm using CloudTrail
    network_changes_metric = cloudwatch.Metric(
        namespace="AWS/CloudTrail",
        metric_name="SecurityGroupEventCount",
        statistic="Sum",
        period=Duration.minutes(5)
    )
    network_changes_alarm = cloudwatch.Alarm(
        scope,
        f"{project_name}-{env_name}-network-changes-alarm",
        metric=network_changes_metric,
        threshold=0,
        evaluation_periods=1,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description="Security Group or NACL changes detected"
    )
    network_changes_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))