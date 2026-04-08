// Pipeline for https://github.com/jreyesromero/basketball_statistics
//
// Feasible setup: connect this repo to Jenkins (Multibranch Pipeline or a Pipeline job
// that builds the `development` branch). On each push to `development`, the stages below
// install dev dependencies and run pytest.
//
// For Multibranch Pipeline, `when { branch 'development' }` matches that branch.
// If BRANCH_NAME is unset (some single-branch jobs), add a job parameter or checkout ref.

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

        stage('Skip — not development') {
            when {
                not {
                    branch 'development'
                }
            }
            steps {
                echo 'Skipping install and tests: current branch is not `development`.'
            }
        }

        stage('Install and test') {
            when {
                branch 'development'
            }
            environment {
                // Required if any test imports src.main (conftest); 32+ characters.
                BASKET_SESSION_SECRET = '0123456789abcdef0123456789abcdef'
            }
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    python -m pip install --upgrade pip
                    pip install -r requirements-dev.txt
                    pytest -q
                '''
            }
        }
    }
}
