@description('Azure region for this cost-conscious learning deployment.')
param location string = resourceGroup().location
@description('Globally unique Container Apps environment name.')
param environmentName string
@description('Container Apps revision image, preferably a pinned ACR image digest.')
param image string
@description('Private ACR login server, for example registry.azurecr.io. Leave empty only for a public image.')
param acrServer string = ''
param appName string = 'opsbridge-telemetry'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${environmentName}-logs'
  location: location
  properties: {
    retentionInDays: 30
    sku: { name: 'PerGB2018' }
  }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource telemetry 'Microsoft.App/containerApps@2026-07-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: empty(acrServer) ? [] : [{ server: acrServer, identity: 'system' }]
      ingress: {
        external: true
        targetPort: 8090
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'telemetry'
          image: image
          env: [{ name: 'PORT', value: '8090' }]
          resources: { cpu: 0.25, memory: '0.5Gi' }
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8090, scheme: 'HTTP' }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

output appUrl string = 'https://${telemetry.properties.configuration.ingress.fqdn}'
output runtimePrincipalId string = telemetry.identity.principalId
