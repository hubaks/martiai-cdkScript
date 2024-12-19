from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_event_sources,
    aws_ec2 as ec2,
    aws_iam as iam,  
    aws_apigatewayv2 as apigatewayv2,
    CfnOutput
)
from aws_cdk import aws_apigateway as apigateway
from constructs import Construct
import aws_cdk.aws_s3 as s3
from aws_cdk import RemovalPolicy
from config import get_database_config, get_env_config, get_project_name, get_pinecone_config

class FileUploadStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, marti_vpc: ec2.Vpc, DatabaseStack, webscrapping_stack,**kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_name = get_env_config()
        config = get_database_config(scope, env_name)
        # Access RDS and Redis connection details
        rds_endpoint = config.database.rds.port
        redis_endpoint = config.database.redis.port

        project_name = get_project_name()
        pinecone_config = get_pinecone_config(scope, env_name)
        s3_bucket = s3.Bucket(
            self, 
            f"{project_name}-{env_name}-FileUploadBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True 
        )
        
        pdf_function = lambda_.Function(
            self, 
            f"{project_name}-{env_name}-PdfFileLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="uploadfile.pdf_file",
            code=lambda_.Code.from_asset("./static"),
            vpc=marti_vpc,
            environment={
                "RDS_ENDPOINT": rds_endpoint,
                "REDIS_ENDPOINT": redis_endpoint,
                "REDIS_PORT": config.database.redis.port,  # Default Redis port
                "PINECONE_API_KEY": pinecone_config.api_key,  # Add your API key here
                "PINECONE_INDEX_NAME": pinecone_config.index_name      # Add your index name here
            }
        )
        
        # Grant the Lambda permission to read from the S3 bucket
        s3_bucket.grant_read(pdf_function)

        # Create the S3 event notification to trigger the Lambda
        s3_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            lambda_event_sources.S3EventSource(pdf_function),
        )

        # Reference the WebSocket API Gateway from the WebsiteScrappingStack
        websocket_api = webscrapping_stack.websocket_api

        # Lambda Integration for WebSocket API
        lambda_integration = apigateway.LambdaIntegration(pdf_function)

        # Add route to the existing WebSocket API (same as WebScraping)
        pdf_route = apigatewayv2.CfnRoute(
            self,
            f"{project_name}-{env_name}-PdfRoute",
            api_id=websocket_api.ref,
            route_key="process-pdf",  
            authorization_type="NONE", 
            target=f"integrations/{lambda_integration.node.id}",
        )

        # Grant the Lambda function permission to be invoked by the API Gateway
        pdf_function.add_permission(
            f"{project_name}-{env_name}-WebSocketInvokePermission",
            principal=apigateway.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.ref}/*"
        )

        # Add necessary policies to the Lambda function to access the WebSocket API
        pdf_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.ref}/*"]
            )
        )

        CfnOutput(
            self, 
            f"{project_name}-{env_name}-PdfApiEndpoint",
            value=websocket_api.attr_api_endpoint,
            description="Endpoint for PDF processing API"
        )