"""IMPULSE AWS infrastructure (AWS CDK v2, Python).

Phase 1 (always deployed): KMS, S3 documents + access logs, DynamoDB, Cognito, RDS PostgreSQL,
Lambda (API / worker / workflow) behind API Gateway HTTP API, EventBridge bus + scheduler,
Step Functions, SNS ops topic, SES identity, CloudTrail, CloudFront + S3 frontend, alarms, budget.

Phase 2/3 services that cost money while idle are OFF unless enabled with CDK context:
  -c enableOpenSearch=true  -c enableLocation=true  -c enableHealthLake=true
  -c enableAppSync=true     -c enableTimestreamInflux=true  -c identityCenterInstanceArn=arn:...
Nothing here creates production resources unless deployed with -c env=prod (explicit approval).
"""
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_budgets as budgets,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cloudtrail as cloudtrail,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_cognito as cognito,
    aws_dynamodb as ddb,
    aws_ec2 as ec2,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_rds as rds,
    aws_s3 as s3,
    aws_ses as ses,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct


class ImpulseStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, env_name: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        prod = env_name == "prod"
        keep = RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY
        ctx = lambda k: str(self.node.try_get_context(k)).lower() == "true"  # noqa: E731

        # ---------- KMS: one customer-managed key for health data, rotation on ----------
        key = kms.Key(self, "DataKey", alias=f"alias/impulse-{env_name}-data", enable_key_rotation=True,
                      description="IMPULSE health data (S3, DynamoDB, RDS, logs, CloudTrail)", removal_policy=keep)
        key.add_to_resource_policy(iam.PolicyStatement(
            principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com"), iam.ServicePrincipal(f"logs.{self.region}.amazonaws.com")],
            actions=["kms:GenerateDataKey*", "kms:Decrypt", "kms:Encrypt", "kms:DescribeKey"], resources=["*"]))

        # ---------- S3: private documents bucket ----------
        access_logs = s3.Bucket(self, "AccessLogs", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                                encryption=s3.BucketEncryption.S3_MANAGED, enforce_ssl=True, removal_policy=keep,
                                auto_delete_objects=not prod,
                                lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(400))])
        docs = s3.Bucket(self, "Documents", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                         encryption=s3.BucketEncryption.KMS, encryption_key=key, bucket_key_enabled=True,
                         enforce_ssl=True, versioned=True, server_access_logs_bucket=access_logs,
                         server_access_logs_prefix="documents/", removal_policy=keep, auto_delete_objects=not prod,
                         object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
                         lifecycle_rules=[s3.LifecycleRule(noncurrent_version_expiration=Duration.days(365),
                                                           abort_incomplete_multipart_upload_after=Duration.days(2))])
        # Malware scanning: enable Amazon GuardDuty Malware Protection for S3 on this bucket (account-level setting).

        # ---------- DynamoDB: idempotency + medication-event mirror ----------
        events_tbl = ddb.Table(self, "MedicationEvents", partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
                               sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
                               billing_mode=ddb.BillingMode.PAY_PER_REQUEST, encryption=ddb.TableEncryption.CUSTOMER_MANAGED,
                               encryption_key=key, point_in_time_recovery=True, removal_policy=keep)
        idem_tbl = ddb.Table(self, "Idempotency", partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
                             billing_mode=ddb.BillingMode.PAY_PER_REQUEST, encryption=ddb.TableEncryption.CUSTOMER_MANAGED,
                             encryption_key=key, time_to_live_attribute="expires_at", removal_policy=keep)

        # ---------- Cognito: patient/caregiver/doctor identities ----------
        pool = cognito.UserPool(self, "Users", self_sign_up_enabled=True, sign_in_aliases=cognito.SignInAliases(email=True),
                                auto_verify=cognito.AutoVerifiedAttrs(email=True),
                                mfa=cognito.Mfa.OPTIONAL, mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=True),
                                password_policy=cognito.PasswordPolicy(min_length=10, require_digits=True, require_lowercase=True,
                                                                       require_uppercase=True, require_symbols=False,
                                                                       temp_password_validity=Duration.days(3)),
                                account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
                                feature_plan=cognito.FeaturePlan.PLUS, removal_policy=keep)
        # Groups describe account type only; patient-level access is enforced by the application.
        for g in ("patient", "caregiver", "doctor_pending", "doctor", "support", "admin"):
            cognito.CfnUserPoolGroup(self, f"Group{g}", user_pool_id=pool.user_pool_id, group_name=g)
        domain = pool.add_domain("Domain", cognito_domain=cognito.CognitoDomainOptions(domain_prefix=f"impulse-{env_name}-{self.account}"))

        # ---------- Network + RDS PostgreSQL ----------
        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=1 if prod else 0,
                      subnet_configuration=[ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC),
                                            ec2.SubnetConfiguration(name="app", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS if prod else ec2.SubnetType.PRIVATE_ISOLATED),
                                            ec2.SubnetConfiguration(name="db", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)])
        for svc, ep in (("s3", ec2.GatewayVpcEndpointAwsService.S3), ("ddb", ec2.GatewayVpcEndpointAwsService.DYNAMODB)):
            vpc.add_gateway_endpoint(f"{svc}Endpoint", service=ep)
        for name, svc in (("secrets", ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER),
                          ("events", ec2.InterfaceVpcEndpointAwsService.EVENTBRIDGE),
                          ("kms", ec2.InterfaceVpcEndpointAwsService.KMS)):
            vpc.add_interface_endpoint(f"{name}Endpoint", service=svc, subnets=ec2.SubnetSelection(subnet_group_name="app"))
        app_sg = ec2.SecurityGroup(self, "AppSg", vpc=vpc, description="IMPULSE Lambdas")
        db_sg = ec2.SecurityGroup(self, "DbSg", vpc=vpc, description="IMPULSE PostgreSQL")
        db_sg.add_ingress_rule(app_sg, ec2.Port.tcp(5432), "Lambdas to PostgreSQL")
        database = rds.DatabaseInstance(
            self, "Postgres", engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM if prod else ec2.InstanceSize.MICRO),
            vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_group_name="db"), security_groups=[db_sg],
            credentials=rds.Credentials.from_generated_secret("impulse"), database_name="impulse",
            storage_encrypted=True, storage_encryption_key=key, multi_az=prod, allocated_storage=20,
            backup_retention=Duration.days(35 if prod else 7), deletion_protection=prod, removal_policy=keep,
            cloudwatch_logs_exports=["postgresql"], iam_authentication=True, auto_minor_version_upgrade=True)

        # ---------- Messaging ----------
        ops_topic = sns.Topic(self, "OpsAlerts", master_key=key, display_name="IMPULSE operational alerts")
        sender = self.node.try_get_context("sesFromAddress")
        if sender:
            ses.EmailIdentity(self, "SenderIdentity", identity=ses.Identity.email(sender))
        bus = events.EventBus(self, "Bus", event_bus_name=f"impulse-{env_name}")
        dlq = sqs.Queue(self, "EventsDlq", encryption=sqs.QueueEncryption.KMS, encryption_master_key=key,
                        retention_period=Duration.days(14))

        # ---------- Lambda functions (one container image, three handlers) ----------
        code = lambda_.DockerImageCode.from_image_asset("../backend")
        env = {
            "ENVIRONMENT": "production" if prod else "staging",
            "DATABASE_SECRET_ARN": database.secret.secret_arn,
            "AUTH_PROVIDER": "cognito",
            "COGNITO_REGION": self.region, "COGNITO_USER_POOL_ID": pool.user_pool_id,
            "COGNITO_DOMAIN": f"{domain.domain_name}.auth.{self.region}.amazoncognito.com",
            "S3_DOCUMENTS_BUCKET": docs.bucket_name, "KMS_KEY_ID": key.key_arn,
            "DYNAMODB_EVENTS_TABLE": events_tbl.table_name, "DYNAMODB_IDEMPOTENCY_TABLE": idem_tbl.table_name,
            "EVENTBRIDGE_BUS_NAME": bus.event_bus_name, "SNS_OPS_TOPIC_ARN": ops_topic.topic_arn,
            "ENABLE_DEMO_LOGIN": "false", "RUN_BACKGROUND_JOBS": "false", "COOKIE_SECURE": "true",
            "SES_FROM_ADDRESS": sender or "",
        }
        common = dict(code=code, vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_group_name="app"), security_groups=[app_sg],
                      memory_size=1024, environment=env, tracing=lambda_.Tracing.ACTIVE,
                      log_retention=logs.RetentionDays.ONE_YEAR if prod else logs.RetentionDays.ONE_MONTH)
        api_fn = lambda_.DockerImageFunction(self, "ApiFn", timeout=Duration.seconds(29), **common)
        worker_fn = lambda_.DockerImageFunction(
            self, "WorkerFn", timeout=Duration.minutes(2), reserved_concurrent_executions=1,  # one tick at a time
            **{**common, "code": lambda_.DockerImageCode.from_image_asset("../backend", cmd=["app.lambda_handler.worker_handler"])})
        wf_fn = lambda_.DockerImageFunction(
            self, "WorkflowFn", timeout=Duration.seconds(60),
            **{**common, "code": lambda_.DockerImageCode.from_image_asset("../backend", cmd=["app.lambda_handler.interaction_workflow_handler"])})
        for fn in (api_fn, worker_fn, wf_fn):
            database.secret.grant_read(fn)
            docs.grant_read_write(fn)
            key.grant_encrypt_decrypt(fn)
            events_tbl.grant_read_write_data(fn)
            idem_tbl.grant_read_write_data(fn)
            bus.grant_put_events_to(fn)
            ops_topic.grant_publish(fn)
            fn.add_to_role_policy(iam.PolicyStatement(actions=["ses:SendEmail", "sms-voice:SendTextMessage"], resources=["*"]))
        api_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["comprehendmedical:DetectEntitiesV2","bedrock:InvokeModel",
                     "geo:SearchPlaceIndexForText", "healthlake:CreateResource", "healthlake:UpdateResource"], resources=["*"]))

        # ---------- Step Functions: interaction assessment follow-up ----------
        notify = tasks.LambdaInvoke(self, "NotifyPrescriber", lambda_function=wf_fn,
                                    payload=sfn.TaskInput.from_object({"assessment_id.$": "$.assessment_id", "step": "notify"}),
                                    result_path="$.notify", retry_on_service_exceptions=True)
        notify.add_retry(errors=["States.ALL"], max_attempts=3, backoff_rate=2, interval=Duration.seconds(5))
        failed = sfn.Fail(self, "WorkflowFailed", cause="Interaction follow-up failed after retries")
        notify.add_catch(tasks.SnsPublish(self, "AlertOps", topic=ops_topic,
                                          message=sfn.TaskInput.from_text("Interaction workflow failed")).next(failed))
        machine = sfn.StateMachine(self, "InteractionWorkflow", timeout=Duration.minutes(5),
                                   definition_body=sfn.DefinitionBody.from_chainable(notify.next(sfn.Succeed(self, "Done"))),
                                   tracing_enabled=True,
                                   logs=sfn.LogOptions(destination=logs.LogGroup(self, "SfnLogs", encryption_key=key), level=sfn.LogLevel.ERROR))
        machine.grant_start_execution(api_fn)
        api_fn.add_environment("SFN_INTERACTION_STATE_MACHINE_ARN", machine.state_machine_arn)

        # ---------- EventBridge: scheduler tick + domain-event archive ----------
        events.Rule(self, "Tick", schedule=events.Schedule.rate(Duration.minutes(1)),
                    targets=[targets.LambdaFunction(worker_fn, dead_letter_queue=dlq, retry_attempts=2)])
        bus.archive("Archive", event_pattern=events.EventPattern(source=["impulse.app"]), retention=Duration.days(90))

        # ---------- API Gateway HTTP API with throttling ----------
        http = apigw.HttpApi(self, "Api", create_default_stage=False)
        http.add_routes(path="/api/{proxy+}", methods=[apigw.HttpMethod.ANY],
                        integration=integrations.HttpLambdaIntegration("ApiIntegration", api_fn))
        stage = apigw.HttpStage(self, "Stage", http_api=http, auto_deploy=True,
                                throttle=apigw.ThrottleSettings(rate_limit=50, burst_limit=100))
        api_fn.add_environment("COGNITO_REDIRECT_URI", "https://REPLACE_WITH_CLOUDFRONT_DOMAIN/api/auth/cognito/callback")

        # ---------- Frontend: S3 + CloudFront; /api/* proxied for same-origin cookies ----------
        site = s3.Bucket(self, "Site", block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
                         encryption=s3.BucketEncryption.S3_MANAGED, removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)
        api_origin = origins.HttpOrigin(f"{http.api_id}.execute-api.{self.region}.amazonaws.com", origin_path="")
        dist = cloudfront.Distribution(
            self, "Cdn", default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(origin=origins.S3BucketOrigin.with_origin_access_control(site),
                                                        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                                                        response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS),
            additional_behaviors={"/api/*": cloudfront.BehaviorOptions(
                origin=api_origin, viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL, cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER)},
            error_responses=[cloudfront.ErrorResponse(http_status=404, response_http_status=200, response_page_path="/index.html")])
        api_fn.add_environment("FRONTEND_ORIGIN", f"https://{dist.distribution_domain_name}")

        # ---------- CloudTrail (AWS API audit; complements the clinical audit log) ----------
        trail_bucket = s3.Bucket(self, "TrailBucket", block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
                                 encryption=s3.BucketEncryption.KMS, encryption_key=key, removal_policy=keep,
                                 auto_delete_objects=not prod, object_lock_enabled=prod)
        trail = cloudtrail.Trail(self, "Trail", bucket=trail_bucket, encryption_key=key, enable_file_validation=True,
                                 include_global_service_events=True, is_multi_region_trail=True,
                                 send_to_cloud_watch_logs=True, cloud_watch_logs_retention=logs.RetentionDays.ONE_YEAR)
        trail.add_s3_event_selector([cloudtrail.S3EventSelector(bucket=docs)], read_write_type=cloudtrail.ReadWriteType.ALL)

        # ---------- Monitoring, alarms, budget ----------
        alarm_action = cw_actions.SnsAction(ops_topic)
        for name, metric in (("ApiErrors", api_fn.metric_errors(period=Duration.minutes(5))),
                             ("WorkerErrors", worker_fn.metric_errors(period=Duration.minutes(5))),
                             ("WorkflowFailures", machine.metric_failed(period=Duration.minutes(5))),
                             ("DlqMessages", dlq.metric_approximate_number_of_messages_visible())):
            cw.Alarm(self, name, metric=metric, threshold=1, evaluation_periods=1).add_alarm_action(alarm_action)
        cw.Alarm(self, "DbStorageLow", metric=database.metric_free_storage_space(), threshold=2 * 1024 ** 3,
                 comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD, evaluation_periods=1).add_alarm_action(alarm_action)
        budget_email = self.node.try_get_context("budgetEmail")
        if budget_email:
            budgets.CfnBudget(self, "Budget", budget=budgets.CfnBudget.BudgetDataProperty(
                budget_type="COST", time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=float(self.node.try_get_context("budgetUsd") or 150), unit="USD")),
                notifications_with_subscribers=[budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(comparison_operator="GREATER_THAN", notification_type="ACTUAL", threshold=80),
                    subscribers=[budgets.CfnBudget.SubscriberProperty(address=budget_email, subscription_type="EMAIL")])])

        # ---------- Optional (cost while idle): enable explicitly ----------
        if ctx("enableOpenSearch"):
            from aws_cdk import aws_opensearchserverless as aoss
            aoss.CfnCollection(self, "DirectorySearch", name=f"impulse-{env_name}-directory", type="SEARCH")
        if ctx("enableLocation"):
            from aws_cdk import aws_location as location
            location.CfnPlaceIndex(self, "Places", index_name=f"impulse-{env_name}-places", data_source="Esri",
                                   data_source_configuration=location.CfnPlaceIndex.DataSourceConfigurationProperty(intended_use="SingleUse"))
        if ctx("enableHealthLake"):
            from aws_cdk import aws_healthlake as healthlake
            healthlake.CfnFHIRDatastore(self, "Fhir", datastore_type_version="R4", datastore_name=f"impulse-{env_name}",
                                        sse_configuration=healthlake.CfnFHIRDatastore.SseConfigurationProperty(
                                            kms_encryption_config=healthlake.CfnFHIRDatastore.KmsEncryptionConfigProperty(
                                                cmk_type="CUSTOMER_MANAGED_KMS_KEY", kms_key_id=key.key_arn)))
        identity_center = self.node.try_get_context("identityCenterInstanceArn")
        if identity_center:
            from aws_cdk import aws_sso as sso
            for ps, policy in (("ImpulseDeveloper", "arn:aws:iam::aws:policy/ReadOnlyAccess"),
                               ("ImpulseAdministrator", "arn:aws:iam::aws:policy/AdministratorAccess")):
                sso.CfnPermissionSet(self, ps, instance_arn=identity_center, name=ps, session_duration="PT4H",
                                     managed_policies=[policy])
            # Developers get read-only infra access and NO data-plane access to the documents bucket or database.

        for k, v in {"ApiUrl": stage.url, "SiteUrl": f"https://{dist.distribution_domain_name}", "SiteBucket": site.bucket_name,
                     "UserPoolId": pool.user_pool_id, "DocumentsBucket": docs.bucket_name, "DbSecretArn": database.secret.secret_arn,
                     "StateMachineArn": machine.state_machine_arn, "OpsTopicArn": ops_topic.topic_arn}.items():
            CfnOutput(self, k, value=v)
