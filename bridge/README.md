# Avena Electrical MCP — Cloud Integration v0.5

**Public MCP endpoint:** `https://elc.avenaai.ir/mcp`

This gateway now implements **OAuth 2.1 authorization-code with PKCE S256**. ChatGPT OAuth discovery metadata is available at:

- `/.well-known/oauth-protected-resource`
- `/.well-known/oauth-protected-resource/mcp`
- `/.well-known/oauth-authorization-server`

ChatGPT registers as a dynamic OAuth client and prompts the Avena owner to authenticate at `/oauth/authorize`. The owner password and Windows pairing token must remain **outside this public repository**.

## Windows

The paired workstation runs AutoCAD and a loopback MCP endpoint at `127.0.0.1:18327`; the cloud server cannot call COM directly.

1. Run the Avena Electrical GUI and start its **local MCP**.
2. Use the GUI's **Connect to ChatGPT** button (v0.5 desktop bundle), or run `bridge/windows/CONNECT_CLOUD.bat`.
3. Enter the separate **Windows agent token** stored on the server at `/etc/avena-elc/bridge.env`. The standalone BAT additionally asks for the local GUI MCP token.
4. In ChatGPT, create a custom MCP connection using the public endpoint, **OAuth** authentication, and complete the consent form.
5. Test `workstation_status`, `autocad_system_status` and `autocad_drawing_info`.

The standalone Python bridge `bridge/windows/stdlib_agent.py` requires Python 3.11+ x64 and **no extra pip packages**. It uses outgoing HTTPS only, so do not open 18327 in a firewall.

## Security and validation

- Remote allowlist is **read-only**: `system_status`, `drawing_info`, `layer_list`, `block_list`.
- Access to `/mcp` requires user-specific OAuth access tokens. OAuth codes have PKCE S256, short expiration and one-time redemption. Refresh tokens rotate.
- The agent uses a *different* private credential for polling. The local MCP itself has a separate token.
- No write/delete/drafting tools are exposed from the cloud.
- Tested remotely: OAuth metadata 200, automatic client registration 201, authorization HTML page 200, unauthenticated MCP 401 with WWW-Authenticate, core OAuth unit tests.
- **Not yet verified:** the complete ChatGPT browser OAuth callback on a live account and COM tools on the actual Windows AutoCAD seat.

Source originates from AutoCAD MCP Pro (MIT) as documented in repository legal notices; the site/product uses Avena Design branding.
