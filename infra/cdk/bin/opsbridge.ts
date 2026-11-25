#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { OpsBridgeLabStack } from '../lib/opsbridge-stack';
import { ServerlessWorkflowStack } from '../lib/serverless-workflow-stack';
const app=new cdk.App();
new OpsBridgeLabStack(app,'OpsBridgeLabStack',{env:{account:process.env.CDK_DEFAULT_ACCOUNT,region:process.env.CDK_DEFAULT_REGION}});
if (process.env.INCLUDE_SERVERLESS_LAB === 'true') {
  new ServerlessWorkflowStack(app,'OpsBridgeServerlessLabStack',{env:{account:process.env.CDK_DEFAULT_ACCOUNT,region:process.env.CDK_DEFAULT_REGION}});
}
