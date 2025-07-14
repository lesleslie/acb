Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/dns/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [DNS](./README.md)

# DNS Adapter

The DNS adapter provides a standardized interface for managing DNS records in ACB applications, with support for cloud DNS providers.

## Overview

The ACB DNS adapter offers a consistent way to manage DNS records:

- Create and manage DNS zones
- Add, update, and delete DNS records
- Support for multiple record types (A, AAAA, TXT, MX, etc.)
- Automated DNS verification for domain ownership
- Cloud provider integration

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Cloud DNS** | Google Cloud DNS implementation | GCP-based applications |
| **Cloudflare** | Cloudflare DNS implementation | Global performance, advanced features |

## Installation

```bash
# Install with DNS support
uv add "acb[dns]"

# Or include it with other dependencies
uv add "acb[dns,storage,sql]"
```

## Configuration

### Settings

Configure the DNS adapter in your `settings/adapters.yml` file:

```yaml
# Use Cloud DNS implementation
dns: cloud_dns

# Or use Cloudflare implementation
dns: cloudflare

# Or disable DNS management
dns: null
```

### DNS Settings

The DNS adapter settings can be customized in your `settings/app.yml` file:

```yaml
dns:
  # Common settings
  zone_name: "example.com"  # Zone name (usually your domain)
  ttl: 300  # DNS TTL (time-to-live) in seconds

  # Cloud DNS specific settings
  project_id: "my-gcp-project"  # Google Cloud project ID

  # Cloudflare specific settings
  api_email: "user@example.com"  # Cloudflare account email
  api_key: "your-api-key"  # Cloudflare API key
  # OR
  api_token: "your-api-token"  # Cloudflare API token (preferred)
  account_id: "your-account-id"  # Required for zone creation
  proxied: false  # Whether to proxy records through Cloudflare
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.adapters.dns import DnsRecord

# Import the DNS adapter
DNS = import_adapter("dns")

# Get the DNS instance via dependency injection
dns = depends.get(DNS)

# Create a DNS record
record = DnsRecord(
    name="www",
    type="A",  # A record for IPv4 address
    ttl=300,   # 5 minutes TTL
    rrdata="203.0.113.1"
)

# Add the record to DNS
await dns.create_records(record)

# Or add multiple records at once
records = [
    DnsRecord(name="api", type="A", rrdata="203.0.113.2"),
    DnsRecord(name="mail", type="MX", rrdata="10 mail.example.com.")
]
await dns.create_records(records)

# List all records
all_records = dns.list_records()
```

## Advanced Usage

### Creating Domain Verification Records

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.adapters.dns import DnsRecord

DNS = import_adapter("dns")
dns = depends.get(DNS)

# Create a verification record for domain ownership
verification_record = DnsRecord(
    name="_acme-challenge",
    type="TXT",
    ttl=60,  # Short TTL for verification tokens
    rrdata="verification-token-from-certificate-authority"
)

await dns.create_records(verification_record)
```

### Managing Email-Related DNS Records

```python
# Set up email records
email_records = [
    # MX record for mail delivery
    DnsRecord(
        name="",  # Apex domain
        type="MX",
        ttl=3600,  # 1 hour
        rrdata=["10 mail.example.com.", "20 backup-mail.example.com."]
    ),

    # SPF record for email authentication
    DnsRecord(
        name="",  # Apex domain
        type="TXT",
        ttl=3600,
        rrdata="v=spf1 include:_spf.example.com -all"
    ),

    # DKIM record for email signing
    DnsRecord(
        name="_dkim._domainkey",
        type="TXT",
        ttl=3600,
        rrdata="v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAO..."
    )
]

await dns.create_records(email_records)
```

### Creating a Zone

```python
# Create a new DNS zone
dns.create_zone()
```

### Cloudflare-Specific Features

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.adapters.dns import DnsRecord

# Import the DNS adapter (configured to use Cloudflare)
DNS = import_adapter("dns")
dns = depends.get(DNS)

# Create a proxied record (traffic routed through Cloudflare)
# This is configured in settings/app.yml with proxied: true
record = DnsRecord(
    name="www",
    type="A",
    ttl=300,
    rrdata="203.0.113.1"
)
await dns.create_records(record)

# Create a zone in Cloudflare
# Requires account_id to be set in settings
dns.create_zone()
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - **Problem**: `AuthenticationError: Failed to authenticate with DNS provider`
   - **Solution**: Verify your cloud provider credentials are correctly configured

2. **Permission Denied**
   - **Problem**: `PermissionError: Permission denied for DNS operations`
   - **Solution**: Check that your service account has the necessary DNS administrator role

3. **Rate Limiting**
   - **Problem**: `RateLimitError: Too many DNS update requests`
   - **Solution**: Batch your DNS changes together and reduce update frequency

4. **Propagation Delays**
   - **Problem**: DNS changes not visible immediately
   - **Solution**: DNS changes can take time to propagate (up to 72 hours, though typically minutes)

## Implementation Details

The DNS adapter implements these core methods:

```python
class DnsBase:
    def create_zone(self) -> None: ...
    def list_records(self) -> list[DnsRecord]: ...
    async def create_records(self, records: list[DnsRecord] | DnsRecord) -> None: ...
```

## Additional Resources

- [Google Cloud DNS Documentation](https://cloud.google.com/dns/docs)
- [Cloudflare DNS Documentation](https://developers.cloudflare.com/dns/)
- [Cloudflare API Documentation](https://developers.cloudflare.com/api/)
- [DNS Best Practices](https://www.cloudflare.com/learning/dns/dns-best-practices/)
- [ACB Adapters Overview](../README.md)
