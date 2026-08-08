# Create self-signed certificate for HTTPS proxy
$cert = New-SelfSignedCertificate -DnsName "localhost", "113.173.192.226" -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(1) -KeyAlgorithm RSA -KeyLength 2048

# Export to PFX
$password = ConvertTo-SecureString -String "password123" -Force -AsPlainText
$pfxPath = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal\ssl\server.pfx"
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $password

# Export to PEM (for Node.js)
$pemPath = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal\ssl\server.pem"
$keyPath = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal\ssl\server.key"
$certPath = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal\ssl\server.crt"

# Get the private key
$privateKey = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
$keyBytes = $privateKey.Key.Export([System.Security.Cryptography.RSACryptoServiceProvider]::ExportPKCS8PrivateKeyBlob)
$keyPem = "-----BEGIN PRIVATE KEY-----`n" + [Convert]::ToBase64String($keyBytes, [Base64FormattingOptions]::InsertLineBreaks) + "`n-----END PRIVATE KEY-----"
$keyPem | Out-File -FilePath $keyPath -Encoding ASCII

# Get the certificate
$certBytes = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
$certPem = "-----BEGIN CERTIFICATE-----`n" + [Convert]::ToBase64String($certBytes, [Base64FormattingOptions]::InsertLineBreaks) + "`n-----END CERTIFICATE-----"
$certPem | Out-File -FilePath $certPath -Encoding ASCII

Write-Host "Certificate created successfully!"
Write-Host "PFX: $pfxPath"
Write-Host "Key: $keyPath"
Write-Host "Cert: $certPath"
