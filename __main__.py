"""An AWS Python Pulumi program"""
import pulumi
from pulumi_aws import iam, sns, lambda_, cloudwatch, secretsmanager, get_caller_identity
import json
import os
import zipfile

# Allow lambda assume role
lambda_role = iam.Role(
    resource_name="lambda-weather-notification", 
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {
                        "Service": "lambda.amazonaws.com",
                    },
                    "Effect": "Allow",
                    "Sid": "allowLambdaAssume",
                }
            ]
        }
    ))

# Create SNS Topic and add email target
sns_topic = sns.Topic("weather-notification")
sns_email_target = sns.TopicSubscription(
    resource_name="weather-notification-email",
    endpoint=os.environ['SNS_EMAIL'],
    protocol="email",
    topic=sns_topic.arn
)

# Create secrets manager variable for API Key
secret = secretsmanager.Secret(
    resource_name="weather-notification-api-key"
)

secret_version = secretsmanager.SecretVersion(
    resource_name="v1",
    secret_id=secret.id,
    secret_string=os.environ['WEATHER_API_KEY']
)

# Zip packages for Lambda layer
with zipfile.ZipFile('layer.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    path = 'function/python/'
    for root, dirs, files in os.walk(path):
        for file in files:
            zipf.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                       os.path.join(path, '..')))

# Load dependencies into a Lambda layer
dependency_layer = lambda_.LayerVersion(
    resource_name='weather-dependencies',
    code=pulumi.FileArchive('layer.zip'),
    layer_name='weather-dependencies',
    compatible_runtimes=['python3.8']
)

with zipfile.ZipFile('lambda.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    zipf.write('./function/index.py', 'index.py')

# Create function
lambda_function = lambda_.Function(
    resource_name="weather-notification",
    code=pulumi.FileArchive('lambda.zip'),
    environment={
        "variables": {
            "TOPIC_ARN": sns_topic.arn,
            "SECRET_ID": secret.id,
            "SECRET_VERSION": secret_version.version_id,
            "ZIP_CODE": os.environ['WEATHER_NOTIFICATION_ZIP_CODE']
        }
    },
    runtime="python3.8",
    role=lambda_role.arn,
    handler="index.lambda_handler",
    layers=[dependency_layer.arn]
)

# Make log group for Lambda function
log_group = cloudwatch.LogGroup(
    resource_name="weather-notification-log-group",
    name=lambda_function.name.apply(
        lambda function_name: "/aws/lambda/" + function_name
    ),
    retention_in_days=7,
    opts=pulumi.ResourceOptions(depends_on=[
        lambda_function
    ])
)

# IAM role for lambda to call SNS publish, 
# push Cloudwatch logs, and secrets manager retrieval
lambda_iam_policy = iam.Policy(
    resource_name="weather-notification-policy",
    opts=pulumi.ResourceOptions(depends_on=[
        log_group,
        sns_topic,
        secret
    ]),
    policy=pulumi.Output.all(sns_arn=sns_topic.arn, log_group_arn=log_group.arn, secret_arn=secret.arn).apply(
        lambda args: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "sns:Publish"
                    ],
                    "Effect": "Allow",
                    "Resource": args['sns_arn']
                },
                {
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Effect": "Allow",
                    "Resource": args['secret_arn']
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": [
                        args['log_group_arn'] + ':*'
                    ]
                }
            ]
        })
    )
)

# Attach policy to role
role_policy_attach = iam.RolePolicyAttachment(
    resource_name="weather-notification",
    role=lambda_role.name,
    policy_arn=lambda_iam_policy.arn
)

execution_role = iam.Role(
    resource_name="cron-weather-notification", 
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {
                        "Service": "lambda.amazonaws.com",
                    },
                    "Effect": "Allow",
                    "Sid": "allowLambdaAssume",
                }
            ]
        }
    ))

# Create Cloudwatch cron job for ~7am PT
cron_rule = cloudwatch.EventRule(
    resource_name='weather-notification-event-rule',
    description='Cron that triggers lambda weather notification',
    schedule_expression='cron(0 13 * * ? *)'
)

# Assign rule to hit target
event_target = cloudwatch.EventTarget(
    resource_name='execute-weather-notification-lambda',
    rule=cron_rule.name,
    arn=lambda_function.arn
)

lambda_alias = lambda_.Alias(
    resource_name="weather-notification-alias",
    description="A weather notification sent to desired email",
    function_name=lambda_function.name,
    function_version="$LATEST"
)

caller = get_caller_identity()

# Allow event bridge to invoke the function
lambda_permission = lambda_.Permission(
    resource_name="allow-event-bridge",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="events.amazonaws.com",
    source_arn=cron_rule.arn,
    qualifier=lambda_alias.name,
    source_account=caller.account_id
)