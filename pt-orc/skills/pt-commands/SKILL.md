---
name: pt-commands
version: "0.72"
description: >
  [v0.72] L3 — CLI command reference for all PT tools, grouped by service/technology.
  Loaded by L2 skills (pt-recon, pt-enum) for specific command groups only. Drop after
  commands executed. Never loaded by L1 directly. Single file — navigate to the relevant
  group section only.
---

<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->

<!-- MRK:SKILL_NAV_TOC — Section index | nav,toc,index | L14-42 -->
<!-- - MRK:PT_CMDS_PASSIVE_CAPTURE — GROUP: PASSIVE / CAPTURE | pt,cmds,passive,capture,group | L43-68 -->
<!-- - MRK:PT_CMDS_DNS_OSINT — GROUP: DNS / OSINT | pt,cmds,dns,osint,group | L69-139 -->
<!-- - MRK:PT_CMDS_SWEEP — GROUP: SWEEP | pt,cmds,sweep,group,nmap | L140-198 -->
<!-- - MRK:PT_CMDS_SMB — GROUP: SMB | pt,cmds,smb,group,cme | L199-228 -->
<!-- - MRK:PT_CMDS_NFS — GROUP: NFS | pt,cmds,nfs,group,showmount | L229-256 -->
<!-- - MRK:PT_CMDS_SNMP — GROUP: SNMP | pt,cmds,snmp,group,snmpwalk | L257-286 -->
<!-- - MRK:PT_CMDS_FTP — GROUP: FTP | pt,cmds,ftp,group,anonymous | L287-322 -->
<!-- - MRK:PT_CMDS_TLS — GROUP: TLS | pt,cmds,tls,group,testssl | L323-356 -->
<!-- - MRK:PT_CMDS_HTTP — GROUP: HTTP | pt,cmds,http,group,headers | L357-401 -->
<!-- - MRK:PT_CMDS_WP — GROUP: WP | pt,cmds,wp,group,wordpress | L402-458 -->
<!-- - MRK:PT_CMDS_SSH — GROUP: SSH | pt,cmds,ssh,group,openssh | L459-480 -->
<!-- - MRK:PT_CMDS_RDP — GROUP: RDP | pt,cmds,rdp,group,nla | L481-499 -->
<!-- - MRK:PT_CMDS_TELNET — GROUP: TELNET | pt,cmds,telnet,group,cleartext | L500-515 -->
<!-- - MRK:PT_CMDS_OOB — GROUP: OOB (IPMI / iLO / iDRAC) | pt,cmds,oob,group,ipmi | L516-538 -->
<!-- - MRK:PT_CMDS_LDAP — GROUP: LDAP | pt,cmds,ldap,group,bloodhound | L539-562 -->
<!-- - MRK:PT_CMDS_DB — GROUP: DB (databases) | pt,cmds,db,group,databases | L563-590 -->
<!-- - MRK:PT_CMDS_VPN — GROUP: VPN | pt,cmds,vpn,group,ike | L591-622 -->
<!-- - MRK:PT_CMDS_NETDEV — GROUP: NETDEV | pt,cmds,netdev,group,cdp | L623-645 -->
<!-- - MRK:PT_CMDS_MQTT — GROUP: MQTT | pt,cmds,mqtt,group,mosquitto | L646-669 -->
<!-- - MRK:PT_CMDS_MSF_REFERENCE — MSF Quick Reference | pt,cmds,msf,reference,quick | L670-699 -->
<!-- - MRK:PT_CMDS_MANUAL_LOG — Manual Session Log Header | pt,cmds,manual,log,session | L700-718 -->
<!-- NAV-LEN: 21 entries | Integrity-hash: 035b53e3d982f53f | Last-indexed: 2026-04-24T20:37:14Z -->

# pt-commands — CLI Reference
*L3 — Navigate to required group. Load only what you need. Drop after use.*

---

## MRK:PT_CMDS_PASSIVE_CAPTURE — GROUP: PASSIVE / CAPTURE | pt,cmds,passive,capture,group | L43-68
*Loaded by: pt-recon (PTI passive, pre-active)*

```bash
# Passive interface listening — traffic capture
tcpdump -i <iface> -w evidence/_captures/<TS>_<iface>_passive.pcapng
tshark -i <iface> -w evidence/_captures/<TS>_<iface>_passive.pcapng

# Capture specific protocols
tshark -i <iface> -f "port 53 or port 67 or port 5353" \
  -w evidence/_captures/<TS>_dhcp_dns_mdns.pcapng

# LLMNR / NBNS observation
tshark -i <iface> -Y "llmnr or nbns" -T fields \
  -e ip.src -e dns.qry.name 2>/dev/null | tee evidence/_captures/<TS>_llmnr_nbns.txt

# ARP table — initial host map from passive observation
arp -a | tee evidence/_sweep/<TS>_arp.txt
ip neigh | tee evidence/_sweep/<TS>_neigh.txt

# Responder (listen-only mode — no poisoning)
responder -I <iface> -A | tee evidence/_captures/<TS>_responder_passive.txt
```

---

## MRK:PT_CMDS_DNS_OSINT — GROUP: DNS / OSINT | pt,cmds,dns,osint,group | L69-139
*Loaded by: pt-recon (PTE external surface mapping)*
*Primary PTE automation: 01_dns_recon.sh + 02_ip_range_analysis.sh — use these commands for supplemental investigation or return passes only.*

```bash
# Subdomain enumeration
subfinder -d <domain> -o evidence/_dns/subfinder_<TS>.txt
amass enum -passive -d <domain> -o evidence/_dns/amass_<TS>.txt

# Certificate transparency
curl -s "https://crt.sh/?q=%25.<domain>&output=json" \
  | python3 -c "import sys,json; [print(h) for h in sorted(set(e['name_value'] for e in json.load(sys.stdin)))]" \
  | tee evidence/_dns/crt_<TS>.txt

# DNS resolution — bulk
cat evidence/_dns/subfinder_<TS>.txt | dnsx -o evidence/_dns/resolved_<TS>.txt

# Zone transfer attempt (always attempt — document result regardless)
dig axfr <domain> @<nameserver> | tee evidence/_dns/axfr_<TS>.txt
# For each NS:
for ns in $(dig ns <domain> +short); do
  dig axfr <domain> @$ns | tee -a evidence/_dns/axfr_all_<TS>.txt
done

# Reverse DNS
dig -x <IP> | tee evidence/_dns/rdns_<IP>_<TS>.txt

# WHOIS / ASN ownership (manual supplement — 06 automates this per-IP)
whois <domain> | tee evidence/_dns/whois_<domain>_<TS>.txt
whois -h whois.radb.net -- '-i origin AS<NUM>' | tee evidence/_dns/asn_<TS>.txt

# HTTP(S) probing on resolved subdomains
httpx -l evidence/_dns/resolved_<TS>.txt -o evidence/_dns/httpx_<TS>.txt \
  -title -tech-detect -status-code

# Shodan (if API key available)
shodan host <IP> | tee evidence/_dns/shodan_host_<IP>_<TS>.txt
shodan domain <domain> | tee evidence/_dns/shodan_domain_<domain>_<TS>.txt

# Censys (if API key available)
curl -s "https://search.censys.io/api/v2/certificates/search" \
  -u "<API_ID>:<API_SECRET>" \
  -G --data-urlencode "q=parsed.names: <domain>" \
  | jq -r '.result.hits[].parsed\.names[]' 2>/dev/null \
  | grep "<domain>" | sort -u | tee evidence/_dns/censys_<domain>_<TS>.txt

# Third-party/CDN check — IPs in these ranges should be excluded from scanning
# Cloudflare: 104.16.0.0/12, 172.64.0.0/13 | Fastly: 151.101.0.0/16
# AWS CF: 13.32.0.0/15, 52.84.0.0/15 | Akamai: 23.0.0.0/12
python3 -c "
import ipaddress
ip = ipaddress.ip_address('<IP>')
third_party = ['104.16.0.0/12','172.64.0.0/13','151.101.0.0/16','13.32.0.0/15','52.84.0.0/15']
print('THIRD-PARTY' if any(ip in ipaddress.ip_network(c) for c in third_party) else 'IN-SCOPE')
"

# Subdomain takeover fingerprint (check response body for known unclaimed strings)
curl -sk --max-time 10 "https://<subdomain>" 2>/dev/null | \
  grep -qi "There isn't a GitHub Pages\|NoSuchBucket\|herokucdn.*no-such-app" && \
  echo "TAKEOVER CANDIDATE: <subdomain>" || echo "No takeover pattern found"

# IP range analysis — manual supplement (02_ip_range_analysis.sh automates all of this)
# BGP info for single IP:
curl -s "https://api.bgpview.io/ip/<IP>" | jq '.data.prefixes[0] | {prefix, name, country_code}' \
  | tee evidence/_ip_analysis/bgp_<IP>_<TS>.json
# Geolocation:
curl -s "https://ip-api.com/json/<IP>" | tee evidence/_ip_analysis/geo_<IP>_<TS>.json
```

---

## MRK:PT_CMDS_SWEEP — GROUP: SWEEP | pt,cmds,sweep,group,nmap | L140-198
*Loaded by: pt-recon (S2 broad sweep — PTI and PTE)*
*Primary sweep automation: 03_comprehensive_scan.sh. These commands are for manual/supplemental use.*
*Tier quick ref: ghost=T2/rate50 · normal=T3/rate1000 · loud=T4/rate3000 · evasion=T1/rate5/-f/--source-port 443/--scan-delay 2s*

```bash
# MSF workspace setup (verify before any command)
msf6 > workspace                           # verify active workspace
msf6 > workspace -a <OrgCode>             # create if not exists
msf6 > spool evidence/_msf/<TS>_console.log

# PTI — optional ARP-only host discovery (local segment only, reliable, no hangs)
# -PR forces ARP; -sn no port scan; -Pn skip ICMP; always ghost tier
db_nmap -PR -sn -Pn -T2 --max-rate 50 --max-retries 1 <CIDR> \
  -oA evidence/_sweep/sweep_arp_<TS>
# IMPORTANT: Never use -sn alone for PTI/PTE main sweep — ICMP ping unreliable,
# causes hangs on OT/fragile hosts. Use -Pn TCP SYN below as primary discovery.

# PTI — TCP SYN scan (primary host discovery + full port scan)
# -Pn: skip host discovery — SYN scan IS the discovery mechanism
db_nmap -sS -sV -O -p- --open -Pn \
  -T2 --max-rate 50 --max-retries 1 --host-timeout 10m \
  <CIDR> -oA evidence/_sweep/nmap_tcp_ghost_<TS>             # ghost tier

db_nmap -sS -sV -O -p- --open -Pn \
  -T3 --min-rate 500 --max-rate 1000 --max-retries 2 --host-timeout 5m \
  <CIDR> -oA evidence/_sweep/nmap_tcp_normal_<TS>            # normal tier

# PTE — TCP SYN scan from target list (01_dns_recon.sh output: scripts/targets.txt)
# -Pn mandatory: external hosts behind FW won't respond to ICMP
db_nmap -sS -sV -O -p- --open -Pn \
  -T2 --max-rate 50 --max-retries 1 --host-timeout 10m \
  -iL scripts/targets.txt -oA evidence/_sweep/nmap_pte_ghost_<TS>     # ghost

db_nmap -sS -sV -O -p- --open -Pn \
  -T1 --max-rate 5 --max-retries 1 --host-timeout 30m \
  -f --source-port 443 --scan-delay 2s --randomize-hosts --data-length 25 -n \
  -iL scripts/targets.txt -oA evidence/_sweep/nmap_pte_evasion_<TS>   # evasion

# PTE — decoys (requires explicit RoE authorisation)
db_nmap -sS -sV -p- --open -Pn -T1 --max-rate 5 \
  -D RND:5 -iL scripts/targets.txt -oA evidence/_sweep/nmap_pte_decoy_<TS>

# PTE — idle/zombie scan (requires RoE authorisation + suitable zombie host)
db_nmap -sI <zombie_IP> -Pn -p- --open \
  -iL scripts/targets.txt -oA evidence/_sweep/nmap_pte_idle_<TS>

# UDP scan — per-host, correlation-driven (derive from TCP findings)
# Automated by 03_comprehensive_scan.sh; manual below for targeted follow-up
db_nmap -sU -sV -Pn -T2 --max-rate 20 --max-retries 1 --host-timeout 10m \
  -p 161,162,123,53,67,68,69,623,500,4500,137,138,2049,111,389 \
  <IP> -oA evidence/_sweep/nmap_udp_<IP>_<TS>

# MSF DB export — ALWAYS include notes (NSE script output stored in notes, not services)
msf6 > hosts    -o evidence/_exports/hosts_<phase>_<TS>.csv
msf6 > services -o evidence/_exports/services_<phase>_<TS>.csv
msf6 > notes    -o evidence/_exports/notes_<phase>_<TS>.csv
```

## MRK:PT_CMDS_SMB — GROUP: SMB | pt,cmds,smb,group,cme | L199-228
*Loaded by: pt-enum for SMB / Windows shares / domain enumeration*

```bash
# SMB discovery and enumeration — nmap scripts
db_nmap -p 445,139 --script smb-os-discovery,smb-enum-shares,smb-enum-users,\
smb-protocols,smb2-security-mode,smb-vuln-ms17-010 \
  <IP> -oA evidence/<IP>/nmap_smb_<TS>

# CrackMapExec — signing, auth, share enum
crackmapexec smb <IP> | tee evidence/<IP>/cme_smb_<TS>.txt
crackmapexec smb <IP> --shares | tee evidence/<IP>/cme_shares_<TS>.txt
crackmapexec smb <IP> -u '' -p '' --shares | tee evidence/<IP>/cme_null_<TS>.txt
# Subnet sweep for signing
crackmapexec smb <CIDR> | tee evidence/_sweep/cme_signing_<TS>.txt

# enum4linux-ng — full enumeration
enum4linux-ng <IP> -oY evidence/<IP>/enum4linux_<TS>.yml
enum4linux-ng <IP> -A | tee evidence/<IP>/enum4linux_full_<TS>.txt

# Manual share access test
smbclient -L //<IP> -N | tee evidence/<IP>/smbclient_list_<TS>.txt
smbclient //<IP>/<share> -N | tee evidence/<IP>/smbclient_<share>_<TS>.txt

# Password policy
crackmapexec smb <IP> --pass-pol | tee evidence/<IP>/cme_passpol_<TS>.txt
```

---

## MRK:PT_CMDS_NFS — GROUP: NFS | pt,cmds,nfs,group,showmount | L229-256
*Loaded by: pt-enum for NFS / network shares*

```bash
# Discover NFS exports
showmount -e <IP> | tee evidence/<IP>/showmount_<TS>.txt
db_nmap -p 111,2049 --script nfs-ls,nfs-showmount,nfs-statfs \
  <IP> -oA evidence/<IP>/nmap_nfs_<TS>

# Mount and inspect (if RoE permits)
mkdir -p /tmp/nfsmount_<IP>
mount -t nfs <IP>:/<export> /tmp/nfsmount_<IP> -o nolock
ls -la /tmp/nfsmount_<IP> | tee evidence/<IP>/nfs_ls_<TS>.txt

# Test write access
touch /tmp/nfsmount_<IP>/ERA_pentest_<TS>.txt 2>&1 | tee evidence/<IP>/nfs_write_<TS>.txt
# IMMEDIATELY remove test file:
rm /tmp/nfsmount_<IP>/ERA_pentest_<TS>.txt

# Clean up
umount /tmp/nfsmount_<IP>

# Note all mount paths, permissions, and observed content in:
# evidence/<IP>/manual_nfs_<TS>.txt (with standard header)
```

---

## MRK:PT_CMDS_SNMP — GROUP: SNMP | pt,cmds,snmp,group,snmpwalk | L257-286
*Loaded by: pt-enum for SNMP / network device information*

```bash
# SNMPv1/v2c with public community
snmpwalk -v1  -c public <IP> | tee  evidence/<IP>/snmpwalk_<TS>.txt
snmpwalk -v2c -c public <IP> | tee -a evidence/<IP>/snmpwalk_<TS>.txt

# Targeted OIDs — system info
snmpget -v2c -c public <IP> sysDescr.0 sysName.0 sysLocation.0 \
  | tee evidence/<IP>/snmp_sys_<TS>.txt

# Interface and routing table
snmpwalk -v2c -c public <IP> ifDescr | tee evidence/<IP>/snmp_iface_<TS>.txt
snmpwalk -v2c -c public <IP> ipRouteTable | tee evidence/<IP>/snmp_routes_<TS>.txt

# Full SNMP check tool
snmp-check <IP> -c public | tee evidence/<IP>/snmpcheck_<TS>.txt

# Community string brute force (if authorised)
onesixtyone -c /usr/share/seclists/Discovery/SNMP/common-snmp-community-strings.txt \
  <IP> | tee evidence/<IP>/snmp_brute_<TS>.txt

# Nmap SNMP scripts
db_nmap -sU -p 161 --script snmp-info,snmp-interfaces,snmp-netstat,snmp-processes \
  <IP> -oA evidence/<IP>/nmap_snmp_<TS>
```

---

## MRK:PT_CMDS_FTP — GROUP: FTP | pt,cmds,ftp,group,anonymous | L287-322
*Loaded by: pt-enum for FTP / anonymous access*

```bash
# Nmap FTP scripts
db_nmap -p 21 --script ftp-anon,ftp-syst,ftp-bounce,banner \
  <IP> -oA evidence/<IP>/nmap_ftp_<TS>

# Manual anonymous login
ftp <IP>
# At prompt: user=anonymous pass=anonymous (or blank)
# Commands to run in session: pwd, ls -la, cd <dir>, get <file>
# Log full session to: evidence/<IP>/manual_ftp_<TS>.txt

# Test write access (STOR)
echo "ERA_pentest_<TS>" > /tmp/era_test.txt
ftp -n <IP> <<EOF | tee evidence/<IP>/ftp_write_test_<TS>.txt
quote USER anonymous
quote PASS anonymous
put /tmp/era_test.txt ERA_pentest_<TS>.txt
quit
EOF
# IMMEDIATELY delete test file via FTP:
ftp -n <IP> <<EOF
quote USER anonymous
quote PASS anonymous
delete ERA_pentest_<TS>.txt
quit
EOF

# Recursive directory listing (curl)
curl -s --user anonymous:anonymous ftp://<IP>/ --list-only | tee evidence/<IP>/ftp_ls_<TS>.txt
```

---

## MRK:PT_CMDS_TLS — GROUP: TLS | pt,cmds,tls,group,testssl | L323-356
*Loaded by: pt-enum for TLS/HTTPS/certificate assessment*
*Primary automation: 04_tls_scan.sh — use these commands for supplemental or single-host investigation.*
*Binary name is `testssl` (no .sh suffix). `--warnings batch` is mandatory to prevent interactive prompts.*

```bash
# Full TLS assessment (binary: testssl, not testssl.sh)
testssl --warnings batch \
        --htmlfile evidence/<IP>/testssl_<port>_<TS>.html \
        --jsonfile  evidence/<IP>/testssl_<port>_<TS>.json \
        --logfile   evidence/<IP>/testssl_<port>_<TS>.log \
        https://<IP>:<port>

# Certificate details only
openssl s_client -connect <IP>:443 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -noout -text | tee evidence/<IP>/cert_<TS>.txt

# Cipher enumeration (nmap)
db_nmap -p 443,8443 --script ssl-enum-ciphers <IP> \
  -oA evidence/<IP>/nmap_tls_<TS>

# Check for legacy protocols (OpenSSL 3.x removed -ssl2/-ssl3 flags — check before use)
# openssl s_client -help 2>&1 | grep -q '\-ssl3' && echo "ssl3 available" || echo "ssl3 removed"
openssl s_client -connect <IP>:443 -tls1   2>&1 | tee evidence/<IP>/tls10_<TS>.txt
openssl s_client -connect <IP>:443 -tls1_1 2>&1 | tee evidence/<IP>/tls11_<TS>.txt
# "unexpected eof" = server rejected = correctly hardened (not an error)

# SSL Labs + Security Headers screenshot capture
python3 scripts/grab_scores_v2.2.py --targets scripts/TARGETS_TLS \
  --output-dir screens/
```

---

## MRK:PT_CMDS_HTTP — GROUP: HTTP | pt,cmds,http,group,headers | L357-401
*Loaded by: pt-enum for HTTP / web application surface*
*Primary web automation: 05_web_enum.sh — use these commands for supplemental or single-host investigation.*
*WordPress detection and assessment: see GROUP: WP below (06_wpscan.sh). Do not run wpscan inline here.*

```bash
# Security headers check
curl -sI https://<target> | tee evidence/<IP>/headers_<TS>.txt
curl -sI http://<target>  | tee evidence/<IP>/headers_http_<TS>.txt

# CORS check (3 origins — mirrors 05_web_enum.sh logic)
curl -sI -H "Origin: https://evil.com" https://<target> | grep -i "access-control" \
  | tee evidence/<IP>/cors_evil_<TS>.txt
curl -sI -H "Origin: null" https://<target> | grep -i "access-control" \
  | tee evidence/<IP>/cors_null_<TS>.txt

# Nikto web scan
nikto -h https://<target> -o evidence/<IP>/nikto_<TS>.txt \
  -Format txt -timeout 10

# Directory and file discovery
gobuster dir -u https://<target> -w /usr/share/wordlists/dirb/common.txt \
  -t 20 -o evidence/<IP>/gobuster_<TS>.txt
ffuf -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -u https://<target>/FUZZ -mc 200,301,302,401,403 \
  -o evidence/<IP>/ffuf_dirs_<TS>.json

# Technology detection
whatweb https://<target> | tee evidence/<IP>/whatweb_<TS>.txt

# API endpoint probe (mirrors 05_web_enum.sh 25-path probe)
for path in /api /api/v1 /api/v2 /swagger /swagger-ui /openapi.json \
            /graphql /admin /health /metrics /actuator /console; do
  code=$(curl -sko /dev/null -w "%{http_code}" "https://<target>${path}")
  [[ "$code" != "404" ]] && echo "${code} ${path}"
done | tee evidence/<IP>/api_endpoints_<TS>.txt

# Authentication brute force (only where authorised)
hydra -L users.txt -P passwords.txt <target> \
  http-post-form "/login:user=^USER^&pass=^PASS^:F=Invalid" \
  | tee evidence/<IP>/hydra_web_<TS>.txt
```

---

## MRK:PT_CMDS_WP — GROUP: WP | pt,cmds,wp,group,wordpress | L402-458
*Loaded by: pt-enum for WordPress detection and security assessment*
*Primary automation: 06_wpscan.sh — use these commands for supplemental or manual follow-up.*
*Output dir: evidence/_wpscan/<label>/ (NOT evidence/<IP>/)*
*Run 06_wpscan.sh after 05_web_enum.sh populates scripts/wp_targets.txt.*

```bash
# Step 1 — Confirm WordPress present (if 05 not yet run)
curl -sk https://<target>/ | grep -qi "wp-content\|wp-login\|wordpress" \
  && echo "WordPress detected" | tee evidence/_wpscan/<label>/wp_detect_<TS>.txt

# Step 2 — WPScan full enumeration (with API token — preferred)
wpscan --url https://<target> \
  --enumerate vp,vt,u,tt,cb,dbe \
  --api-token <WPSCAN_API_TOKEN> \
  -o evidence/_wpscan/<label>/wpscan_full_<TS>.txt

# Without API token (no CVE detail — detection/enum still works)
wpscan --url https://<target> \
  --enumerate vp,vt,u,tt,cb,dbe \
  -o evidence/_wpscan/<label>/wpscan_basic_<TS>.txt

# Evasion / ghost tier — add throttle
wpscan --url https://<target> \
  --enumerate vp,vt,u,tt,cb,dbe \
  --throttle 2000 --max-threads 1 \
  --api-token <WPSCAN_API_TOKEN> \
  -o evidence/_wpscan/<label>/wpscan_full_<TS>.txt

# Step 3 — XML-RPC probe (brute-force vector check)
curl -sk -X POST "https://<target>/xmlrpc.php" \
  -d '<?xml version="1.0"?><methodCall><methodName>system.listMethods</methodName></methodCall>' \
  | grep -q "methodResponse" \
  && echo "XML-RPC ENABLED" | tee evidence/_wpscan/<label>/xmlrpc_<TS>.txt \
  || echo "XML-RPC not responding" | tee evidence/_wpscan/<label>/xmlrpc_<TS>.txt

# Step 4 — REST API user enumeration
curl -sk "https://<target>/wp-json/wp/v2/users" \
  | tee evidence/_wpscan/<label>/wpjson_users_<TS>.txt

# Step 5 — Config file exposure (critical if any return 200)
for path in /wp-config.php /wp-config.php.bak /.wp-config.php.swp \
            /wp-content/debug.log /readme.html /license.txt \
            /wp-admin/install.php /wp-login.php; do
  code=$(curl -sko /dev/null -w "%{http_code}" "https://<target>${path}")
  echo "${code} ${path}"
done | tee evidence/_wpscan/<label>/config_exposure_<TS>.txt

# Step 6 — wp-admin exposure + rate-limit headers
curl -skI "https://<target>/wp-admin/" | tee evidence/_wpscan/<label>/wpadmin_<TS>.txt

# Note: sanitize <label> from URL — strip protocol, replace /.: with _
# e.g. https://example.com/wp → example_com_wp
```

---

## MRK:PT_CMDS_SSH — GROUP: SSH | pt,cmds,ssh,group,openssh | L459-480
*Loaded by: pt-enum for SSH version, config, CVE assessment*

```bash
# Banner and version grab
nc -nv <IP> 22 2>&1 | head -5 | tee evidence/<IP>/ssh_banner_<TS>.txt
ssh -vvv <IP> 2>&1 | head -50 | tee evidence/<IP>/ssh_verbose_<TS>.txt

# Nmap SSH scripts
db_nmap -p 22 --script ssh-auth-methods,ssh-hostkey,ssh2-enum-algos \
  <IP> -oA evidence/<IP>/nmap_ssh_<TS>

# Check for CVE-2024-6387 (regreSSHion) — version check
# Affected: OpenSSH < 4.4p1 (unless patched), 8.5p1–9.7p1 (excl. 9.7p1)
ssh -V 2>&1 | tee evidence/<IP>/ssh_version_<TS>.txt

# Algorithm negotiation (identify weak algorithms)
nmap -p 22 --script ssh2-enum-algos <IP> | tee evidence/<IP>/ssh_algos_<TS>.txt
```

---

## MRK:PT_CMDS_RDP — GROUP: RDP | pt,cmds,rdp,group,nla | L481-499
*Loaded by: pt-enum for RDP / remote desktop*

```bash
# RDP enumeration
db_nmap -p 3389 --script rdp-enum-encryption,rdp-vuln-ms12-020 \
  <IP> -oA evidence/<IP>/nmap_rdp_<TS>

# NLA check (Network Level Authentication)
nmap -p 3389 --script rdp-enum-encryption <IP> \
  | grep -i "NLA\|Security\|Encryption" | tee evidence/<IP>/rdp_nla_<TS>.txt

# BlueKeep / DejaBlue check (safe check only — no exploit)
db_nmap -p 3389 --script rdp-vuln-ms12-020 <IP> \
  -oA evidence/<IP>/nmap_rdp_vuln_<TS>
```

---

## MRK:PT_CMDS_TELNET — GROUP: TELNET | pt,cmds,telnet,group,cleartext | L500-515
*Loaded by: pt-enum for Telnet (legacy / network devices)*

```bash
# Detect Telnet
db_nmap -p 23 --script telnet-encryption,banner <IP> \
  -oA evidence/<IP>/nmap_telnet_<TS>

# Manual banner grab
nc -nv <IP> 23 2>&1 | tee evidence/<IP>/telnet_banner_<TS>.txt

# Note: Telnet = cleartext. Capture traffic on the wire if pcap active.
```

---

## MRK:PT_CMDS_OOB — GROUP: OOB (IPMI / iLO / iDRAC) | pt,cmds,oob,group,ipmi | L516-538
*Loaded by: pt-enum for IPMI / iLO / iDRAC / out-of-band management*

```bash
# IPMI enumeration
db_nmap -p 623 --script ipmi-version,ipmi-cipher-zero <IP> \
  -oA evidence/<IP>/nmap_ipmi_<TS>

# iLO / iDRAC web interface
curl -sk https://<IP>/login | tee evidence/<IP>/ilo_login_<TS>.txt
curl -skI https://<IP>/ | tee evidence/<IP>/ilo_headers_<TS>.txt

# IPMI cipher zero (authentication bypass — if detected safe to verify)
ipmitool -I lanplus -C 0 -H <IP> -U admin -P "" user list \
  | tee evidence/<IP>/ipmi_cipher0_<TS>.txt

# RomPager identification (HP iLO)
curl -sk https://<IP>/ | grep -i "rompager\|ilo\|version" \
  | tee evidence/<IP>/ilo_version_<TS>.txt
```

---

## MRK:PT_CMDS_LDAP — GROUP: LDAP | pt,cmds,ldap,group,bloodhound | L539-562
*Loaded by: pt-enum for Active Directory / LDAP enumeration*

```bash
# LDAP anonymous bind check
ldapsearch -x -H ldap://<IP> -b "" -s base namingContexts \
  | tee evidence/<IP>/ldap_base_<TS>.txt

# Full anonymous enumeration
ldapsearch -x -H ldap://<IP> -b "DC=<domain>,DC=<tld>" \
  | tee evidence/<IP>/ldap_anon_<TS>.txt

# Domain users (with creds if authorised)
ldapsearch -x -H ldap://<IP> -D "<user>@<domain>" -W \
  -b "DC=<domain>,DC=<tld>" "(objectClass=user)" \
  | tee evidence/<IP>/ldap_users_<TS>.txt

# BloodHound collection (with creds — if authorised)
bloodhound-python -u <user> -p <pass> -d <domain> \
  -c All --zip -o evidence/<IP>/bloodhound_<TS>.zip
```

---

## MRK:PT_CMDS_DB — GROUP: DB (databases) | pt,cmds,db,group,databases | L563-590
*Loaded by: pt-enum for exposed database services*

```bash
# MSSQL
db_nmap -p 1433 --script ms-sql-info,ms-sql-empty-password,ms-sql-config \
  <IP> -oA evidence/<IP>/nmap_mssql_<TS>

# MySQL
db_nmap -p 3306 --script mysql-info,mysql-empty-password,mysql-databases \
  <IP> -oA evidence/<IP>/nmap_mysql_<TS>
mysql -h <IP> -u root --password= -e "show databases;" \
  | tee evidence/<IP>/mysql_anon_<TS>.txt

# PostgreSQL
db_nmap -p 5432 --script pgsql-brute <IP> \
  -oA evidence/<IP>/nmap_pgsql_<TS>

# MongoDB (unauthenticated)
mongosh <IP>:27017 --eval "db.adminCommand('listDatabases')" \
  | tee evidence/<IP>/mongo_<TS>.txt
# Fallback if mongosh not installed:
mongo <IP>:27017 --eval "db.adminCommand('listDatabases')" \
  | tee evidence/<IP>/mongo_<TS>.txt
```

---

## MRK:PT_CMDS_VPN — GROUP: VPN | pt,cmds,vpn,group,ike | L591-622
*Loaded by: pt-enum for VPN / gateway / firewall assessment*

```bash
# IKE/IPSec enumeration
db_nmap -p 500,4500 -sU --script ike-version <IP> \
  -oA evidence/<IP>/nmap_ike_<TS>
ike-scan <IP> | tee evidence/<IP>/ikescan_<TS>.txt

# Zyxel specific — CVE-2023-28771 (pre-auth RCE via IKEv2)
# Affected: ZLD <= 5.36 Patch 1 on USG FLEX, VPN, ATP series
# IMPORTANT: Firmware version string is REQUIRED before confirming severity.
# Without version confirmation: mark [Precautionary], confidence LIKELY.
# Version check: obtain ZLD version string from client or web interface banner.
curl -sk https://<IP>/cgi-bin/boardDataWWW.php 2>/dev/null \
  | tee evidence/<IP>/zyxel_info_<TS>.txt
curl -sk https://<IP>/ | grep -i "version\|zld\|zyxel" \
  | tee evidence/<IP>/zyxel_banner_<TS>.txt

# Zyxel CVE-2024-42057 — command injection via VPN
# Requires authentication or specific condition — confirm version first

# FortiGate
curl -sk https://<IP>/remote/login | tee evidence/<IP>/forti_login_<TS>.txt
curl -skI https://<IP>/ | tee evidence/<IP>/forti_headers_<TS>.txt

# SSL-VPN portal fingerprint
curl -sk https://<IP>:10443/ | tee evidence/<IP>/sslvpn_<TS>.txt
```

---

## MRK:PT_CMDS_NETDEV — GROUP: NETDEV | pt,cmds,netdev,group,cdp | L623-645
*Loaded by: pt-enum for network device enumeration (switches, routers)*

```bash
# CDP / LLDP capture
tshark -i <iface> -f "ether proto 0x88cc or ether[20:2] == 0x2000" \
  -w evidence/_captures/<TS>_cdp_lldp.pcapng

# SNMP on network devices — see SNMP group for commands

# Telnet to device — see TELNET group for commands

# SSH to device
ssh -o StrictHostKeyChecking=no admin@<IP> 2>&1 \
  | tee evidence/<IP>/ssh_netdev_<TS>.txt

# Default credential test (manual — log full session)
# Common defaults: admin/admin, admin/password, cisco/cisco, enable/enable
# Log to: evidence/<IP>/manual_netdev_creds_<TS>.txt
```

---

## MRK:PT_CMDS_MQTT — GROUP: MQTT | pt,cmds,mqtt,group,mosquitto | L646-669
*Loaded by: pt-enum for MQTT broker assessment*

```bash
# MQTT connection attempt (unauthenticated)
mosquitto_sub -h <IP> -p 1883 -t '#' -v --quiet \
  | tee evidence/<IP>/mqtt_subscribe_<TS>.txt &
sleep 30; kill %1

# MQTT with TLS
mosquitto_sub -h <IP> -p 8883 -t '#' -v --insecure \
  | tee evidence/<IP>/mqtt_tls_<TS>.txt &
sleep 30; kill %1

# Nmap MQTT scripts
db_nmap -p 1883,8883 --script mqtt-subscribe <IP> \
  -oA evidence/<IP>/nmap_mqtt_<TS>

# Test publish (if write access to be verified — RoE check required)
mosquitto_pub -h <IP> -p 1883 -t 'era/pentest' -m 'ERA_PT_test_<TS>'
```

---

## MRK:PT_CMDS_MSF_REFERENCE — MSF Quick Reference | pt,cmds,msf,reference,quick | L670-699
*Available in any session — not a group, always accessible*

```bash
# Workspace management
msf6 > workspace                           # show active
msf6 > workspace <OrgCode>               # switch to engagement
msf6 > spool evidence/_msf/<TS>_console.log

# DB queries
msf6 > hosts
msf6 > services
msf6 > services -p 445
msf6 > notes -h <IP>

# Add caveat note
msf6 > notes -a -h <IP> -t db.caveat \
  -d "Port 8443 identified as HTTP; confirmed HTTPS manually"

# Export — ALWAYS include notes (NSE script output stored in notes, not services)
msf6 > hosts    -o evidence/_exports/hosts_<phase>_<TS>.csv
msf6 > services -o evidence/_exports/services_<phase>_<TS>.csv
msf6 > notes    -o evidence/_exports/notes_<phase>_<TS>.csv

# Import scan results
msf6 > db_import evidence/<IP>/nmap_<TS>.xml
```

---

## MRK:PT_CMDS_MANUAL_LOG — Manual Session Log Header | pt,cmds,manual,log,session | L700-718
*Use at the start of every `manual_<desc>_<TS>.txt` file*

```
# Manual Session Log
# Engagement:  <OrgCode>
# Target:      <IP>:<port> / <hostname>
# Date/Time:   <YYYY-MM-DD HH:MM>
# Tester:      Greg Gordon / TechGuard.
# Objective:   <what this session tests>
# RoE notes:   <any relevant restrictions>
---
```

---
*pt-commands SKILL.md v0.72 — L3 | dispatched by pt-enum and pt-recon*

<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
