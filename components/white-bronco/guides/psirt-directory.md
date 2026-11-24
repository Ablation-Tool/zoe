# PSIRT / Security Disclosure Contact Directory

Vendor and coordinator contacts for coordinated vulnerability disclosure (CVD). Verify
contacts before sending — vendors occasionally change portals without notice. Last
verified: 2026-09.

---

## Coordinators

Use a coordinator when the vendor is unresponsive, the scope is multi-vendor, or the
vulnerability affects critical infrastructure.

| Organization | Portal / Email | Notes |
|---|---|---|
| **CISA VINCE-NT** | https://vulnerabilities.cisa.gov/vincent/auth/login/ | Preferred for ICS/OT and multi-vendor CVD. Replaced kb.cert.org/vince. Also: cvd@cisa.dhs.gov |
| **CERT/CC (CMU)** | https://kb.cert.org/vince/ | Legacy; active for academic/research cases. |
| **ICS-CERT** | https://www.cisa.gov/reporting-ics-cyber-incident | Parallel channel for ICS/OT advisories. CISA subsumes this. |
| **FIRST** | https://www.first.org/coordination/ | Connects you to vendor PSIRT teams via FIRST membership. |

---

## Networking / Security Appliances

| Vendor | Email | Portal | Notes |
|---|---|---|---|
| **Cisco** | psirt@cisco.com | https://sec.cloudapps.cisco.com/security/center/home.x | PGP: key on their site. Phone: +1-408-525-6532 |
| **Fortinet** | Web form only | https://www.fortiguard.com/faq/psirt-contact | PGP key ID: 0xC7A59F07. Advisory cadence: monthly. |
| **Palo Alto Networks** | psirt@paloaltonetworks.com | https://security.paloaltonetworks.com/report | PGP key on their site. |
| **Juniper Networks** | sirt@juniper.net | https://advisory.juniper.net | PGP encouraged. Called SIRT, not PSIRT. |
| **F5 Networks** | f5sirt@f5.com | https://www.f5.com/support/report-a-vulnerability | Include product, version, PoC in first email. |
| **SonicWall** | psirt@sonicwall.com | https://psirt.global.sonicwall.com | |
| **Check Point** | cp_response@checkpoint.com | https://www.checkpoint.com/support-services/contact-support/ | |
| **Aruba Networks (HPE)** | aruba-sirt@hpe.com | https://www.arubanetworks.com/support-services/security-bulletins/ | |

---

## Enterprise IT / Software

| Vendor | Email | Portal | Notes |
|---|---|---|---|
| **Microsoft (MSRC)** | — | https://msrc.microsoft.com/report/vulnerability | Portal only; no direct email intake. |
| **Google** | — | https://bughunters.google.com/report | Portal only. Bug bounty program. |
| **Apple** | — | https://security.apple.com/bounty | Portal only. security@apple.com for general inquiries only. |
| **IBM PSIRT** | psirt@us.ibm.com | https://www.ibm.com/trust/security-vulnerability-management | PGP available. |
| **Oracle** | secalert_us@oracle.com | https://www.oracle.com/corporate/security-practices/assurance/vulnerability/reporting/ | PGP available. Quarterly CPU patch cycle. |
| **VMware / Broadcom** | vmware.psirt@broadcom.com | https://www.broadcom.com/support/resources/product-security-center | PGP key: legacyId=1055 on Broadcom knowledge base. |
| **SAP** | secure@sap.com | https://www.sap.com/about/trust-center/security/incident-management.html | PGP available. |
| **Atlassian** | security@atlassian.com | https://www.atlassian.com/trust/security/vulnerability-reporting | Bug bounty on Bugcrowd. |
| **GitLab** | — | https://gitlab.com/gitlab-org/gitlab/-/issues (HackerOne) | Via HackerOne. |
| **Adobe** | psirt@adobe.com | https://helpx.adobe.com/security.html | Patch Tuesdays. |
| **SolarWinds** | psirt@solarwinds.com | https://www.solarwinds.com/information-security | |
| **Ivanti** | secure@ivanti.com | https://www.ivanti.com/support/contact-security | Bug bounty on Bugcrowd. |
| **Citrix / NetScaler** | Submission via portal | https://www.netscaler.com/community (Security tab) | No direct email published; use community portal. |

---

## Infrastructure / Cloud

| Vendor | Email | Portal | Notes |
|---|---|---|---|
| **Amazon AWS** | — | https://aws.amazon.com/security/vulnerability-reporting/ | No email; portal only. |
| **Akamai** | vulnerability-disclosure@akamai.com | https://www.akamai.com/legal/responsible-disclosure | |
| **Cloudflare** | — | https://hackerone.com/cloudflare | HackerOne program. |
| **HashiCorp** | security@hashicorp.com | https://www.hashicorp.com/security | |
| **Red Hat** | secalert@redhat.com | https://access.redhat.com/security/team/contact/ | PGP available. |

---

## Hardware / Workstations / Servers

| Vendor | Email | Portal | Notes |
|---|---|---|---|
| **HPE (Hewlett Packard Enterprise)** | security-alert@hpe.com | https://hpe.com/info/report-security-vulnerability | security-alert@hpe.com for encrypted/file submissions. security@hpe.com for general issues. |
| **HP Inc.** | — | https://www.hp.com/h41268/live/index.aspx?qid=25434 | Consumer products. |
| **Dell Technologies** | secure@dell.com | https://www.dell.com/en-us/dt/corporate/privacy-policy/dell-vulnerability-disclosure-policy.htm | PGP available. |
| **Lenovo** | psirt@lenovo.com | https://www.lenovo.com/us/en/learn/page/product-security | |
| **Intel** | secure@intel.com | https://www.intel.com/content/www/us/en/security-center/vulnerability-handling-guidelines.html | Intel Platform Update (IPU) quarterly cycle. |
| **AMD** | psirt@amd.com | https://www.amd.com/en/resources/product-security.html | |
| **NVIDIA** | psirt@nvidia.com | https://www.nvidia.com/en-us/product-security/ | |
| **Qualcomm** | product-security@qualcomm.com | https://www.qualcomm.com/company/product-security | |
| **ARM** | psirt@arm.com | https://developer.arm.com/support/arm-security-updates | |

---

## ICS / OT / Industrial

ICS/OT disclosures: **always report to CISA VINCE-NT in parallel** with the vendor.
CISA publishes ICS-CERT advisories (ICSA-YY-DDD-NN) after coordinated disclosure.

| Vendor | Email | Portal | Notes |
|---|---|---|---|
| **Siemens ProductCERT** | productcert@siemens.com | https://productcert.siemens.com | PGP key on site. Patch Tuesdays + quarterly ICS advisories. |
| **Schneider Electric CPCERT** | CPCERT@se.com | https://www.se.com/ww/en/work/support/cybersecurity/report-a-vulnerability/ | PGP fingerprint: 1917 BD57 E2B2 C97E 5257 DACB 804A D638 5567 E958. Monthly advisories. |
| **Rockwell Automation** | rasecure@ra.rockwell.com | https://www.rockwellautomation.com/en-us/trust-center/security-advisories.html | |
| **Honeywell PSIRT** | PSIRT@honeywell.com | https://www.honeywell.com/us/en/product-security | |
| **ABB** | HackerOne (private) | https://global.abb/group/en/technology/cyber-security/report-security-vulnerabilities | Private HackerOne program. |
| **Emerson** | cybersecurity@emerson.com | https://www.emerson.com/en-us/about-us/cybersecurity-commitment | |
| **GE Vernova / GE Grid Solutions** | PSIRT@ge.com | https://www.ge.com/digital/cyber-security | |
| **Mitsubishi Electric** | Psirt@meau.com | https://www.mitsubishielectric.com/en/psirt/ | |
| **Phoenix Contact** | PSIRT@phoenixcontact.com | https://www.phoenixcontact.com/en-pc/service-and-support/psirt | |
| **Moxa** | psirt@moxa.com | https://www.moxa.com/en/support/product-support/security-advisory | |
| **AVEVA** | security@aveva.com | https://www.aveva.com/en/legal/security-vulnerabilities/ | |

---

## Telecom / Semiconductor

| Vendor | Email | Portal | Notes |
|---|---|---|---|
| **Ericsson** | psirt@ericsson.com | https://www.ericsson.com/en/security | |
| **Nokia** | product-security@nokia.com | https://www.nokia.com/notices/responsible-disclosure/ | |
| **Huawei** | psirt@huawei.com | https://www.huawei.com/en/psirt | PGP available. |
| **NXP Semiconductors** | psirt@nxp.com | https://www.nxp.com/support/support/product-security-vulnerability:PSIRT | |
| **Broadcom** | security@broadcom.com | https://www.broadcom.com/support/resources/product-security-center | Separate from VMware channel above. |

---

## Tips

- **Coordinate with CISA VINCE-NT** for any ICS/OT finding regardless of whether you email the vendor directly. CISA issues the ICSA advisory number.
- **PGP-encrypt first emails** to vendors that offer a key — many PSIRT teams require it for initial contact.
- **45–90 days** is the accepted window before public disclosure. State your timeline clearly in the first email.
- **If no response in 7 days**, follow up once. After 14 days of silence, escalate to CISA or CERT/CC.
- **HackerOne / Bugcrowd programs** listed for some vendors are the preferred intake channel even when an email also exists.
