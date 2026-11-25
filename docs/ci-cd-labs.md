# CI/CD learning examples

All four pipeline definitions share the same deterministic frontend build gate:

```sh
npm ci
npm run build:frontends
```

The command builds the Next.js worker portal and careers site, React operations dashboard, Angular compliance console, Vue integration console, and React frontend-patterns lab. The pipeline definitions only build artifacts; they do not deploy or access provider secrets.

| CI system | File | Setup needed to run it |
|---|---|---|
| GitHub Actions | `.github/workflows/integration-e2e.yml` | GitHub runner; this workflow also starts the local Compose backend and runs Playwright E2E. |
| Jenkins | `Jenkinsfile` | Jenkins Pipeline and Docker Pipeline plugins, plus an agent allowed to run the `node:22.22.3` container. |
| GitLab CI | `.gitlab-ci.yml` | GitLab project and a runner that can execute the configured Node container image. |
| Bitbucket Pipelines | `bitbucket-pipelines.yml` | Bitbucket Cloud repository with Pipelines enabled. |

The Jenkins file follows Declarative Pipeline syntax and executes a checked-in pipeline definition. GitLab expects `.gitlab-ci.yml` at the repository root. Bitbucket Pipelines reads `bitbucket-pipelines.yml` from the repository root. See the [Jenkinsfile guide](https://www.jenkins.io/doc/book/pipeline/jenkinsfile/), [GitLab CI YAML reference](https://docs.gitlab.com/ci/yaml/), and [Bitbucket Pipelines guide](https://support.atlassian.com/bitbucket-cloud/docs/get-started-with-bitbucket-pipelines/).

**Verification:** `npm run build:frontends` completed locally with all six builds passing. GitLab, Bitbucket, and Jenkins have not been connected to hosted CI services, so their provider-specific execution has not been verified. GitHub Actions is configured but its full Docker/Playwright workflow also needs a runner execution.
