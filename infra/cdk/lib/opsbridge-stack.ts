import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as kms from 'aws-cdk-lib/aws-kms';

export class OpsBridgeLabStack extends cdk.Stack {
  constructor(scope:Construct,id:string,props?:cdk.StackProps){
    super(scope,id,props);
    const key=new kms.Key(this,'DocumentKey',{enableKeyRotation:true,description:'OpsBridge portfolio document encryption'});
    const deadLetters=new sqs.Queue(this,'DeadLetters',{queueName:'opsbridge-lab-dlq',retentionPeriod:cdk.Duration.days(14),encryption:sqs.QueueEncryption.KMS_MANAGED});
    const queue=new sqs.Queue(this,'DomainEvents',{queueName:'opsbridge-lab-events',visibilityTimeout:cdk.Duration.seconds(120),retentionPeriod:cdk.Duration.days(14),deadLetterQueue:{queue:deadLetters,maxReceiveCount:5},encryption:sqs.QueueEncryption.KMS_MANAGED});
    const topic=new sns.Topic(this,'Notifications',{topicName:'opsbridge-lab-notifications',masterKey:kms.Alias.fromAliasName(this,'SnsKey','alias/aws/sns')});
    const documents=new s3.Bucket(this,'Documents',{encryption:s3.BucketEncryption.KMS,encryptionKey:key,blockPublicAccess:s3.BlockPublicAccess.BLOCK_ALL,versioned:true,enforceSSL:true,removalPolicy:cdk.RemovalPolicy.RETAIN,lifecycleRules:[{noncurrentVersionExpiration:cdk.Duration.days(90)}]});
    new cdk.CfnOutput(this,'DocumentBucketName',{value:documents.bucketName});
    new cdk.CfnOutput(this,'DomainEventsQueueUrl',{value:queue.queueUrl});
    new cdk.CfnOutput(this,'NotificationsTopicArn',{value:topic.topicArn});
  }
}
