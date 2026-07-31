# Private remote access with Tailscale

Tailscale lets MCP clients reach the local server without opening a public router
port. DocColab stays on loopback; Tailscale Serve terminates Tailnet HTTPS.

## Host setup

Install Tailscale, sign in, and choose a stable machine hostname:

```powershell
tailscale up --hostname=doccolab
tailscale status
```

Enable HTTPS certificates/Serve in the Tailnet admin console if prompted, then:

```powershell
tailscale serve --bg http://127.0.0.1:8765
tailscale serve status
```

The MCP URL is normally:

```text
https://doccolab.<your-tailnet>.ts.net/mcp
```

Add that exact hostname and origin to `mcp-config.json`:

```json
{
  "allowed_hosts": [
    "127.0.0.1:*",
    "localhost:*",
    "doccolab.your-tailnet.ts.net"
  ],
  "allowed_origins": [
    "http://127.0.0.1:*",
    "http://localhost:*",
    "https://doccolab.your-tailnet.ts.net"
  ]
}
```

Do not set the DocColab host to `0.0.0.0`. Do not disable DNS-rebinding
protection.

## Tailnet access policy

Restrict TCP 443 to the people/devices that use DocColab. A current Tailscale
Grants policy can use a tagged server:

```json
{
  "groups": {
    "group:doccolab-users": [
      "alice@example.com",
      "bob@example.com"
    ]
  },
  "tagOwners": {
    "tag:doccolab": ["autogroup:admin"]
  },
  "grants": [
    {
      "src": ["group:doccolab-users"],
      "dst": ["tag:doccolab"],
      "ip": ["tcp:443"]
    }
  ]
}
```

Apply `tag:doccolab` to the host through your organization’s approved Tailscale
enrollment process. Policy syntax and identity rules may change; validate the
policy in the admin console before applying it.

## Layered authentication

Both checks are required:

1. Tailscale admits the device/user to the host on 443.
2. DocColab validates the per-user bearer token and role.

Removing Tailnet access does not revoke a token, and rotating a token does not
remove a device from the Tailnet. Perform both actions during offboarding.

## Google webhook limitation

Tailscale Serve is private. Google Drive’s webhook infrastructure cannot connect
to it. Use DocColab’s metadata polling for an all-private deployment. If low
latency webhooks are mandatory, deploy a small public HTTPS relay that validates
Google channel tokens and forwards only normalized event identifiers to the
local agent; that relay is a separate security boundary.
