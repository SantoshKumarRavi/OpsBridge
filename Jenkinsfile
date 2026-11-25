pipeline {
    agent {
        docker {
            image 'node:22.22.3'
        }
    }
    options {
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
    }
    stages {
        stage('Install locked dependencies') {
            steps {
                sh 'npm ci --no-audit --no-fund'
            }
        }
        stage('Build frontends') {
            steps {
                sh 'npm run build:frontends'
            }
        }
    }
    post {
        always {
            deleteDir()
        }
    }
}
