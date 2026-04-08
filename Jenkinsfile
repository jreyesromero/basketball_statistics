// Example pipeline for https://github.com/jreyesromero/basketball_statistics
// Copy this file to the app repo root as `Jenkinsfile` and commit.

pipeline {
    agent any

    options {
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    python -m pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }
    }
}
