import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as cloudfrontOrigins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as glue from 'aws-cdk-lib/aws-glue';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';

/** Opt-in, synthetic-data exercises for AWS services not used by the core ECS stack. */
export class ServerlessWorkflowStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const handler = new lambda.Function(this, 'SyntheticAssessmentFunction', {
      runtime: lambda.Runtime.NODEJS_22_X,
      handler: 'index.handler',
      timeout: cdk.Duration.seconds(5),
      code: lambda.Code.fromInline([
        'exports.handler = async (event) => ({',
        "  caseId: String(event.caseId || 'synthetic-case'),",
        "  status: 'review_required',",
        '  humanDecisionRequired: true,',
        "  explanation: 'Synthetic workflow only; a person owns the final decision.'",
        '});',
      ].join('\n')),
    });

    const assess = new tasks.LambdaInvoke(this, 'AssessSyntheticCase', {
      lambdaFunction: handler,
      payloadResponseOnly: true,
    });
    const humanReview = new sfn.Pass(this, 'HumanReviewRequired', {
      result: sfn.Result.fromObject({ status: 'review_required', humanDecisionRequired: true }),
    });
    assess.addCatch(humanReview, { errors: ['States.ALL'], resultPath: '$.failure' });
    const workflow = new sfn.StateMachine(this, 'SyntheticCaseWorkflow', {
      stateMachineType: sfn.StateMachineType.EXPRESS,
      definitionBody: sfn.DefinitionBody.fromChainable(assess),
      timeout: cdk.Duration.minutes(2),
    });

    const api = new apigateway.RestApi(this, 'SyntheticWorkflowApi', {
      restApiName: 'OpsBridge Synthetic Workflow Lab',
      description: 'IAM-authorized API Gateway entry to a Step Functions Express workflow.',
      deployOptions: { stageName: 'lab', tracingEnabled: true },
    });
    api.root.addResource('workflow').addMethod(
      'POST',
      apigateway.StepFunctionsIntegration.startExecution(workflow),
      { authorizationType: apigateway.AuthorizationType.IAM },
    );

    const staticSite = new s3.Bucket(this, 'StaticDemoSite', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    new s3deploy.BucketDeployment(this, 'StaticDemoContent', {
      destinationBucket: staticSite,
      sources: [s3deploy.Source.data('index.html', '<!doctype html><html><meta charset="utf-8"><title>OpsBridge AWS lab</title><body><h1>OpsBridge static demo</h1><p>Synthetic learning environment.</p></body></html>')],
    });
    const cdn = new cloudfront.Distribution(this, 'StaticDemoCdn', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: cloudfrontOrigins.S3BucketOrigin.withOriginAccessControl(staticSite),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
    });

    const imageRepository = new ecr.Repository(this, 'WorkerImageRepository', {
      repositoryName: 'opsbridge-learning-worker',
      imageScanOnPush: true,
      imageTagMutability: ecr.TagMutability.IMMUTABLE,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const etlScriptBucket = new s3.Bucket(this, 'GlueScriptBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    new s3deploy.BucketDeployment(this, 'GlueScriptDeployment', {
      destinationBucket: etlScriptBucket,
      destinationKeyPrefix: 'scripts',
      sources: [s3deploy.Source.asset('glue')],
    });
    const glueRole = new iam.Role(this, 'GlueJobRole', {
      assumedBy: new iam.ServicePrincipal('glue.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSGlueServiceRole')],
    });
    etlScriptBucket.grantReadWrite(glueRole);
    new glue.CfnJob(this, 'SyntheticReconciliationJob', {
      name: 'opsbridge-synthetic-reconciliation-lab',
      role: glueRole.roleArn,
      glueVersion: '4.0',
      command: {
        name: 'pythonshell',
        pythonVersion: '3.9',
        scriptLocation: `s3://${etlScriptBucket.bucketName}/scripts/reconcile.py`,
      },
      maxCapacity: 0.0625,
      timeout: 5,
      description: 'Dormant ETL exercise; the job is not scheduled or run by this stack.',
    });

    new cdk.CfnOutput(this, 'WorkflowApiUrl', { value: `${api.url}workflow` });
    new cdk.CfnOutput(this, 'CloudFrontDemoUrl', { value: `https://${cdn.distributionDomainName}` });
    new cdk.CfnOutput(this, 'EcrRepositoryUri', { value: imageRepository.repositoryUri });
    new cdk.CfnOutput(this, 'GlueScriptBucketName', { value: etlScriptBucket.bucketName });
  }
}
