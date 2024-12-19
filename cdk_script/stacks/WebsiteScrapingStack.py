from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_event_sources,
    aws_apigateway as apigateway,
    aws_apigatewayv2 as apigatewayv2,
    aws_ec2 as ec2,
    aws_iam as iam
)
from constructs import Construct
from aws_cdk import RemovalPolicy
from database_stack import DatabaseStack    # RDS and Redis components
from config import get_database_config, get_env_config, get_project_name, get_pinecone_config
class WebsiteScrappingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, marti_vpc: ec2.IVpc, database_stack,**kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Access RDS and Redis connection details
        env_name = get_env_config()
        project_name = get_project_name(scope)
        config = get_database_config(scope, env_name)
        pinecone_config = get_pinecone_config(scope, env_name)
        # Access RDS and Redis connection details
        rds_endpoint = config.database.rds.port
        redis_endpoint = config.database.redis.port

        # Create Dead Letter Queue
        dlq = sqs.Queue(
            self,
            f"{project_name}-{env_name}-website_scrappingDLQ",
            queue_name="website-scrapping-dlq",
            removal_policy=RemovalPolicy.DESTROY
        )
        sns_queue = sqs.Queue(self,
                                f"{project_name}-{env_name}-website_scrappingSQS",
                                queue_name="website-scrapping-sqs",
                                dead_letter_queue=sqs.DeadLetterQueue(
                                max_receive_count=2,
                                queue=dlq
                                    ),
                                RemovalPolicy = RemovalPolicy.DESTROY)
        create_job_lambda = lambda_.Function(self,
            f"{project_name}-{env_name}-scrapping-lambda",
            vpc = marti_vpc,
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="uploadfile.sample_lamdba_function",
            code=lambda_.Code.from_asset("./static"),
            environment=dict(
                QUEUE_URL=sns_queue.queue_url,
                RDS_ENDPOINT=rds_endpoint,
                REDIS_ENDPOINT=redis_endpoint,
                REDIS_PORT=config.database.redis.port,  # Default Redis port
                PINECONE_API_KEY=pinecone_config.api_key,
                PINECONE_INDEX_NAME=pinecone_config.index_name
            )
        )
        # Grant the Lambda function permission to read messages from the SQS queue
        sns_queue.grant_consume_messages(create_job_lambda)

        # Add SQS as an event source for the Lambda function
        create_job_lambda.add_event_source(
            lambda_event_sources.SqsEventSource(sns_queue)
        )

        # Grant permissions for RDS and ElastiCache
        create_job_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "rds:DescribeDBInstances",
                    "rds:Connect",
                    "elasticache:Connect",
                    "elasticache:DescribeCacheClusters"
                ],
                resources=[
                    database_stack.rds_arn,
                    database_stack.redis_arn
                ]
            )
        )

        websocket_api = apigatewayv2.CfnApi(
            self,
            f"{project_name}-{env_name}-WebSocketApi",
            name="WebsiteScrappingWebSocketApi",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
        )
        # connect route to connect user
        connect_route = apigatewayv2.CfnRoute(
            self,
            f"{project_name}-{env_name}-ConnectRoute",
            api_id=websocket_api.ref,
            route_key="$connect",
            authorization_type="NONE",
            target=f"integrations/{lambda_integration.logical_id}",
        )
        #disconnec route once user job done
        disconnect_route = apigatewayv2.CfnRoute(
            self,
            f"{project_name}-{env_name}-DisconnectRoute",
            api_id=websocket_api.ref,
            route_key="$disconnect",
            authorization_type="NONE",
            target=f"integrations/{lambda_integration.logical_id}",
        )
        # filestatus route to send file status to client
        send_message_route = apigatewayv2.CfnRoute(
            self,
            f"{project_name}-{env_name}-FileStatusRoute",
            api_id=websocket_api.ref,
            route_key="filestatus",
            authorization_type="NONE",
            target=f"integrations/{lambda_integration.logical_id}",
        )
        lambda_integration = apigatewayv2.CfnIntegration(
            self,
            f"{project_name}-{env_name}-LambdaWebSocketIntegration",
            api_id=websocket_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=create_job_lambda.function_arn,
        )
        # adding permission and policy to lamdba to use apigate way.
        create_job_lambda.add_permission(
            "WebSocketInvokePermission",
            principal=apigateway.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.ref}/*"
        )
        create_job_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.ref}/*"]
            )
        )

        # Grant the Lambda function permissions for RDS and ElastiCache Redis
        create_job_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "rds:*",  # Adjust based on required actions (e.g., rds:DescribeDBInstances, rds:Connect)
                    "elasticache:*"  # Adjust based on required actions (e.g., elasticache:Connect, elasticache:DescribeCacheClusters)
                ],
                resources=["*"]  # Ideally, specify ARNs for your RDS and Redis resources
            )
        )