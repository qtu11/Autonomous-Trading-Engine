$pwd = ConvertTo-SecureString -String 'password123' -Force -AsPlainText
$cert = Import-PfxCertificate -FilePath 'C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal\ssl\server.pfx' -CertStoreLocation 'Cert:\CurrentUser\My' -Password $pwd
$key = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
$keyBytes = $key.Key.Export([System.Security.Cryptography.CspParameters]::ExportKeyBlob)
$keyBase64 = [Convert]::ToBase64String($keyBytes)
Write-Host "PRIVATE KEY:"
Write-Host $keyBase64
