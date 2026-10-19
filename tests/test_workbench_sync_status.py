"""The sync status names the cause a reviewer can act on."""

def test_sync_error_leads_with_the_server_refusal_not_the_ipv6_route():
    """Measured 2026-10-01: libpq reported an IPv6 'Cannot assign requested
    address' first while every IPv4 address said the Neon quota was exceeded."""
    from forensic_metascience_ai_toolkit.workbench.remote import describe_error
    quota = 'ERROR:  Your account or project has exceeded the quota. Upgrade your plan to increase limits.'
    ipv6 = 'Cannot assign requested address\n\tIs the server running on that host and accepting TCP/IP connections?'
    lines = ['connection is bad: connection to server at "2600::1", port 5432 failed: ' + ipv6,
             'Multiple connection attempts failed. All failures were:']
    for addr in ('18.0.0.1', '16.0.0.2', '13.0.0.3'):
        lines.append(f"- host: 'ep.neon.tech', port: None, hostaddr: '{addr}': connection failed: connection to server at \"{addr}\", port 5432 failed: {quota}")
    for addr in ('2600::1', '2600::2'):
        lines.append(f"- host: 'ep.neon.tech', port: None, hostaddr: '{addr}': connection is bad: connection to server at \"{addr}\", port 5432 failed: {ipv6}")
    text = describe_error(OSError('\n'.join(lines)))
    assert text.startswith('OSError: the database server refused the connection: Your account or project has exceeded the quota')
    assert '(3 of 5 addresses; 2 other(s) unreachable: Cannot assign requested address)' in text
    assert text.endswith(ipv6)  # the full libpq text is kept after the lead
    only_network = '\n'.join(l for l in lines if quota not in l)
    assert 'no address of the database server was reachable: Cannot assign requested address (2 of 2' in describe_error(OSError(only_network))
    assert describe_error(ValueError('plain')) == 'ValueError: plain'
