param(
    [int]$ConfigPort = 18888,
    [int]$RegistryPort = 18761,
    [int]$ProviderAPort = 18101,
    [int]$ProviderBPort = 18102,
    [int]$CallerPort = 18090
)

$ErrorActionPreference = 'Stop'
$javaPath = (Get-Command java.exe).Source
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$labRoot = (Resolve-Path (Join-Path $repoRoot 'services/spring-cloud-discovery-lab')).Path
$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) "opsbridge-discovery-$([guid]::NewGuid().ToString('N'))"
$processes = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Assert-PortFree([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $Port is already in use by process $($listener[0].OwningProcess). Choose another port with a script parameter."
    }
}

function Start-LabApp([string]$Name, [string]$JarPath, [string[]]$ApplicationArgs) {
    if (-not (Test-Path -LiteralPath $JarPath -PathType Leaf)) {
        throw "Missing JAR: $JarPath. Build first with mvn -f services/spring-cloud-discovery-lab/pom.xml package."
    }

    $arguments = @('-jar', ('"' + $JarPath + '"')) + $ApplicationArgs
    $process = Start-Process `
        -FilePath $javaPath `
        -ArgumentList $arguments `
        -WorkingDirectory $labRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logRoot "$Name.out.log") `
        -RedirectStandardError (Join-Path $logRoot "$Name.err.log") `
        -PassThru
    $processes.Add($process)
    Write-Host "Started $Name (PID $($process.Id))"
}

function Wait-Http([string]$Url, [int]$ExpectedCount = -1) {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        foreach ($process in $processes) {
            $process.Refresh()
            if ($process.HasExited) {
                throw "A lab process exited early with code $($process.ExitCode); inspect logs under $logRoot"
            }
        }
        try {
            $result = Invoke-RestMethod -Uri $Url -TimeoutSec 3
            if ($ExpectedCount -lt 0 -or @($result).Count -eq $ExpectedCount) {
                return ,$result
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for $Url"
}

foreach ($port in @($ConfigPort, $RegistryPort, $ProviderAPort, $ProviderBPort, $CallerPort)) {
    Assert-PortFree $port
}
New-Item -ItemType Directory -Path $logRoot | Out-Null

try {
    Start-LabApp 'config-server' `
        (Join-Path $labRoot 'config-server/target/config-server-1.0.0.jar') `
        @("--server.port=$ConfigPort")
    Start-LabApp 'registry' `
        (Join-Path $labRoot 'registry/target/service-registry-1.0.0.jar') `
        @("--server.port=$RegistryPort")

    Wait-Http "http://localhost:$ConfigPort/actuator/health" | Out-Null
    Wait-Http "http://localhost:$RegistryPort/actuator/health" | Out-Null
    $registryUrl = "http://localhost:$RegistryPort/eureka/"
    Start-LabApp 'provider-a' `
        (Join-Path $labRoot 'provider/target/synthetic-provider-1.0.0.jar') `
        @(
            "--server.port=$ProviderAPort",
            '--spring.application.name=synthetic-provider',
            '--spring.cloud.config.name=synthetic-provider',
            "--spring.cloud.config.uri=http://localhost:$ConfigPort",
            '--logging.level.org.springframework.cloud.config.client=DEBUG',
            "--eureka.client.service-url.defaultZone=$registryUrl",
            '--eureka.instance.instance-id=provider-a',
            '--eureka.instance.hostname=localhost',
            '--eureka.instance.prefer-ip-address=false',
            "--eureka.instance.non-secure-port=$ProviderAPort"
        )
    Start-LabApp 'provider-b' `
        (Join-Path $labRoot 'provider/target/synthetic-provider-1.0.0.jar') `
        @(
            "--server.port=$ProviderBPort",
            '--spring.application.name=synthetic-provider',
            '--spring.cloud.config.name=synthetic-provider',
            "--spring.cloud.config.uri=http://localhost:$ConfigPort",
            '--logging.level.org.springframework.cloud.config.client=DEBUG',
            "--eureka.client.service-url.defaultZone=$registryUrl",
            '--eureka.instance.instance-id=provider-b',
            '--eureka.instance.hostname=localhost',
            '--eureka.instance.prefer-ip-address=false',
            "--eureka.instance.non-secure-port=$ProviderBPort"
        )

    Wait-Http "http://localhost:$ProviderAPort/actuator/health" | Out-Null
    Wait-Http "http://localhost:$ProviderBPort/actuator/health" | Out-Null
    Start-LabApp 'caller' `
        (Join-Path $labRoot 'caller/target/discovery-caller-1.0.0.jar') `
        @(
            "--server.port=$CallerPort",
            '--spring.application.name=discovery-caller',
            '--spring.cloud.config.name=discovery-caller',
            "--spring.cloud.config.uri=http://localhost:$ConfigPort",
            '--logging.level.org.springframework.cloud.config.client=DEBUG',
            "--eureka.client.service-url.defaultZone=$registryUrl"
        )
    Wait-Http "http://localhost:$CallerPort/actuator/health" | Out-Null
    & python (Join-Path $repoRoot 'scripts/verify_spring_cloud_discovery.py') `
        --config-url "http://localhost:$ConfigPort" `
        --registry-url "http://localhost:$RegistryPort" `
        --caller-url "http://localhost:$CallerPort"
    if ($LASTEXITCODE -ne 0) {
        throw "Spring Cloud E2E checker failed with exit code $LASTEXITCODE"
    }
}
catch {
    Write-Host "Verification failed: $($_.Exception.Message)" -ForegroundColor Red
    Get-ChildItem -LiteralPath $logRoot -File -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "--- $($_.Name) ---"
        Get-Content -LiteralPath $_.FullName -Tail 40
    }
    throw
}
finally {
    foreach ($process in $processes) {
        $process.Refresh()
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
