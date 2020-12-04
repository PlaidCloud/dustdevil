#!/usr/bin/env groovy

@Field 
def image_name = "gcr.io/plaidcloud-build/flashback-service"

@Field
def branch = ""

podTemplate(label: 'dustdevil',
  containers: [
    containerTemplate(name: 'docker', image: 'docker:18.09.9-git', ttyEnabled: true, command: 'cat')
  ],
  serviceAccount: 'jenkins'
)
{
  node(label: 'dustdevil') {
    properties([
      parameters([
        booleanParam(name: 'no_cache', defaultValue: false, description: 'Adds --no-cache flag to docker build command(s).'),
        booleanParam(name: 'full_lint', defaultValue: true, description: 'Perform full lint on a PR build.')
      ])
    ])
    container('docker') {
      withCredentials([string(credentialsId: 'docker-server-ip', variable: 'host')]) {
        docker.withServer("$host", "docker-server") {
          withCredentials([dockerCert(credentialsId: 'docker-server', variable: "DOCKER_CERT_PATH")]) {
            docker.withRegistry('https://gcr.io', 'gcr:plaidcloud-build') {
              // Checkout source before doing anything else
              scm_map = checkout scm

              // When building from a PR event, we want to read the branch name from the CHANGE_BRANCH binding. This binding does not exist on branch events.
              branch = env.CHANGE_BRANCH ?: scm_map.GIT_BRANCH.minus(~/^origin\//)

              docker_args = ''

              // Add any extra docker build arguments here.
              if (params.no_cache) {
                docker_args += '--no-cache'
              }

              stage('Build Image') {
                image = docker.build("${image_name}:test", "--pull ${docker_args} .")
              }

              stage('Run Linter') {
                if (branch == 'master' || params.full_lint) {
                  image.withRun('-t', 'bash -c "pylint dustdevil -j 0 -f parseable -r no>pylint.log"') {c ->
                    sh """
                      docker wait ${c.id}
                      docker cp ${c.id}:/tmp/dustdevil/pylint.log pylint.log
                    """
                  }
                  recordIssues tool: pyLint(pattern: 'pylint.log')
                } else {
                  image.withRun('-t') {c ->
                    sh """
                      docker wait ${c.id}
                      docker cp ${c.id}:/tmp/dustdevil/pylint.log pylint.log
                    """
                  }
                  recordIssues tool: pyLint(pattern: 'pylint.log'), qualityGates: [[threshold: 1, type: 'TOTAL_HIGH', unstable: true]]
                }
              }

              stage('Run Tests') {
                image.withRun("-t", "pytest") {c ->
                  sh """
                    docker wait ${c.id}
                    docker cp ${c.id}:/tmp/dustdevil/pytestresult.xml pytestresult.xml
                    docker cp ${c.id}:/tmp/dustdevil/coverage.xml coverage.xml
                  """
                }
                junit 'pytestresult.xml'
                cobertura coberturaReportFile: 'coverage.xml', onlyStable: false, failUnhealthy:false, failUnstable: false, failNoReports: false
              }

              if (branch == 'master') {
                stage('Trigger Downstream Jobs') {
                  build job: 'plaid/master', parameters: [booleanParam(name: 'no_cache', value: true)], wait: false
                }
              }
            }
          }
        }
      }
    }
  }
}
