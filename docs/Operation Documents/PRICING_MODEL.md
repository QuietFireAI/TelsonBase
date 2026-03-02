# TelsonBase Pricing Model

**Version:** 1.0 | **Status:** Internal Strategy Document | **Date:** February 23, 2026
**Owner:** Jeff Phillips (quietfire) | **Classification:** Confidential

---

## Table of Contents

1. [Pricing Philosophy](#1-pricing-philosophy)
2. [Tier Structure](#2-tier-structure)
3. [Deployment Options](#3-deployment-options)
4. [Add-on Services](#4-add-on-services)
5. [Competitive Comparison](#5-competitive-comparison)
6. [Revenue Projections](#6-revenue-projections)
7. [Discount Programs](#7-discount-programs)

---

## 1. Pricing Philosophy

TelsonBase pricing is built on four principles:

**Value-based pricing tied to compliance risk reduction.** Law firms face regulatory exposure measured in millions of dollars -- malpractice liability, data breach penalties, client trust erosion. TelsonBase pricing reflects the value of reducing that exposure, not the marginal cost of compute. A firm paying $400/seat/month for compliance infrastructure that prevents a single breach has already recouped years of licensing cost.

**Self-hosted means lower total cost of ownership.** Unlike cloud SaaS platforms that pass infrastructure costs (and margins) through to customers, TelsonBase deploys on hardware the customer already owns or controls. There is no cloud egress pricing, no storage tiering surprises, and no vendor lock-in to a specific cloud provider. The customer's data never leaves their network, which is a decisive advantage for attorney-client privilege and HIPAA-regulated workflows.

**No per-API-call pricing.** AI agent platforms that charge per API call create unpredictable costs and discourage adoption. TelsonBase uses flat per-seat pricing. Customers can run as many agents, workflows, and compliance checks as their deployment supports without worrying about a usage bill at the end of the month.

**Predictable, plannable costs.** Every tier is a fixed monthly per-seat rate. No hidden fees, no bandwidth surcharges, no surprise overages. Firms can budget for TelsonBase the same way they budget for any other per-seat software license.

---

## 2. Tier Structure

### Starter -- $150/seat/month (minimum 5 seats)

The entry point for firms that need AI agent orchestration with baseline security and audit capabilities.

| Capability | Detail |
|---|---|
| Core platform | Agent orchestration, QMS messaging, Toolroom with Foreman |
| Audit chain | Cryptographic SHA-256 hash-linked audit trail, Redis-persisted |
| RBAC | Role-based access control across all endpoints |
| Multi-tenancy | Up to 3 tenants with client-matter isolation |
| Authentication | Per-user auth with bcrypt, account lockout, password strength validation |
| Support | Email support, business hours (M-F, 9am-5pm ET) |
| Updates | Community release channel |

**Best for:** Real estate brokerages entering AI agent workflows, small law firms (under 10 attorneys), solo practitioners with support staff, firms evaluating the platform before scaling.

**Monthly range:** $750 (5 seats) to $3,000 (20 seats)

---

### Professional -- $400/seat/month (minimum 10 seats)

The primary revenue tier. Built for law firms and compliance-driven organizations that need the full regulatory infrastructure.

| Capability | Detail |
|---|---|
| Everything in Starter | All core platform features |
| Unlimited tenants | No cap on tenants or client matters |
| Compliance suite | HIPAA/HITECH, HITRUST CSF controls, breach notification workflows |
| MFA enforcement | Mandatory TOTP MFA with backup codes, encrypted secret storage |
| Session management | HIPAA-compliant automatic logoff, configurable idle timeouts |
| Rate limiting | Tenant-scoped Redis sliding window (600/min default, per-user 120/min) |
| Legal holds | Litigation hold management with client-matter scope |
| Data retention | Configurable retention policies per tenant |
| Breach notification | Automated breach detection and notification pipeline |
| Support | Priority support with 8-hour SLA |
| Compliance reports | Quarterly compliance posture reports |

**Best for:** Mid-size law firms (10-50 attorneys), healthcare-adjacent legal practices, firms with HIPAA obligations, real estate firms scaling into regulated transactions.

**Monthly range:** $4,000 (10 seats) to $20,000 (50 seats)

---

### Enterprise -- $750-1,000/seat/month (custom agreement)

For large firms and regulated industries that require dedicated engineering support, custom compliance modules, and audit-ready infrastructure.

| Capability | Detail |
|---|---|
| Everything in Professional | Full compliance suite and platform features |
| Dedicated deployment engineer | Named engineer for installation, configuration, and ongoing optimization |
| Custom compliance modules | Development of firm-specific compliance workflows (CJIS, PCI DSS, GDPR, sanctions screening) |
| SOC 2 Type II audit support | Evidence collection, control mapping, auditor liaison for Type II certification |
| 24/7 support | Round-the-clock support with 2-hour SLA for critical issues |
| HA architecture | High availability consultation and implementation (Docker Swarm or Kubernetes) |
| Pen test coordination | Annual penetration test scoping, coordination, and remediation tracking |
| Disaster recovery | DR testing, RPO/RTO validation, documented recovery procedures |
| Custom SLA | Negotiable uptime commitments and escalation paths |

**Best for:** Large law firms (50+ attorneys), AmLaw 200 firms, firms in regulated industries (healthcare, financial services, government contracting), multi-office deployments.

**Monthly range:** $37,500 (50 seats at $750) to $100,000+ (100 seats at $1,000)

---

## 3. Deployment Options

### Self-Managed Deployment

The customer deploys and maintains TelsonBase on their own infrastructure.

| Item | Detail |
|---|---|
| Deployment target | Customer-owned hardware (Drobo/NAS, on-premise server, private cloud VM) |
| Requirements | Docker Compose, PostgreSQL, Redis (all included in stack) |
| Setup | Customer follows deployment guide; email support available |
| Maintenance | Customer handles OS patching, backups, hardware |
| Cost | Tier pricing only, no additional infrastructure fees |
| Responsibility | Shared responsibility model -- TelsonBase secures software, customer secures environment |

**Recommended for:** Firms with existing IT staff or managed service providers. Lowest total cost of ownership.

### Managed Deployment

Quietfire AI deploys and maintains the TelsonBase instance on the customer's infrastructure.

| Item | Detail |
|---|---|
| Setup fee | $2,000 (Starter), $3,500 (Professional), $5,000 (Enterprise) |
| Deployment | Quietfire AI engineer provisions Docker stack on customer hardware or VM |
| Includes | TLS configuration, secrets generation, backup scheduling, monitoring setup |
| Ongoing maintenance | OS patching coordination, backup verification, upgrade deployment |
| Monthly surcharge | 10% of tier pricing |
| Responsibility | Quietfire AI manages the full stack; customer provides hardware and network access |

**Recommended for:** Firms without dedicated IT staff. Higher cost but turnkey operation.

---

## 4. Add-on Services

Available to any tier as supplementary purchases.

| Add-on | Price | Detail |
|---|---|---|
| Additional compliance modules | $50/seat/month | Custom compliance module (e.g., CJIS, PCI DSS, GDPR, sanctions) added to Starter or Professional tier |
| HA architecture setup | $5,000 - $10,000 one-time | Docker Swarm or Kubernetes HA deployment, failover configuration, data replication |
| Custom integration development | $200/hour | Integration with existing firm systems (DMS, billing, practice management, CRM) |
| Training and onboarding | $2,500/day | On-site or remote training for administrators and end users |
| Data migration assistance | $3,000 - $8,000 one-time | Migration of existing data from legacy systems into TelsonBase |
| Annual pen test coordination | $5,000/engagement | Scoping, vendor coordination, remediation tracking (does not include pen test vendor fees) |
| DR test execution | $1,500/test | Guided disaster recovery test with documentation and RPO/RTO measurement |

---

## 5. Competitive Comparison

| Feature | TelsonBase Professional | Clio Manage | iManage Work | Relativity One |
|---|---|---|---|---|
| **Monthly cost (20 seats)** | $8,000 | $13,900+ ($69.50/user + add-ons) | Custom (est. $15,000+) | Custom (est. $20,000+) |
| **Deployment model** | Self-hosted | Cloud only | Cloud or on-premise | Cloud only |
| **Data residency** | Customer-controlled | Vendor cloud | Vendor cloud or on-premise | Vendor cloud |
| **AI agent orchestration** | Native | Third-party add-ons | Limited | Limited |
| **Cryptographic audit chain** | Yes (SHA-256, hash-linked) | Basic audit log | Basic audit log | Audit log |
| **HIPAA compliance suite** | Built-in (12 modules) | Limited | Limited | Partial |
| **HITRUST controls** | Built-in | No | No | No |
| **Breach notification** | Automated pipeline | Manual | Manual | Manual |
| **MFA enforcement** | Built-in, mandatory at Professional tier | Optional add-on | Available | Available |
| **Multi-tenancy** | Native, unlimited at Professional | Per-account | Per-account | Per-workspace |
| **Litigation holds** | Built-in, matter-scoped | Limited | Yes | Yes |
| **Attorney-client privilege** | Preserved (data never leaves network) | Data on vendor servers | Depends on deployment | Data on vendor servers |
| **Source-available / inspectable** | Full source on customer hardware | Proprietary, no inspection | Proprietary | Proprietary |

**Key differentiators:**
- TelsonBase is the only platform in this comparison that combines AI agent orchestration with a full compliance infrastructure at a self-hosted price point.
- Attorney-client privilege is structurally preserved because data never transits third-party infrastructure.
- The compliance suite (HIPAA, HITRUST, breach notification, legal holds, data retention, sanctions screening) is built in, not bolted on.
- Firms retain full control over their deployment, data, and upgrade cadence.

---

## 6. Revenue Projections

### Conservative (Year 1)

| Scenario | Firms | Avg Seats | Tier | MRR | ARR |
|---|---|---|---|---|---|
| Early traction | 5 | 15 | Professional ($400) | $30,000 | $360,000 |
| Moderate growth | 10 | 20 | Professional ($400) | $80,000 | $960,000 |
| With Starter mix | 10 Pro + 15 Starter | 15 avg | Mixed | $71,250 | $855,000 |

### Growth (Year 2)

| Scenario | Firms | Avg Seats | Tier | MRR | ARR |
|---|---|---|---|---|---|
| Scaling | 25 | 20 | Professional ($400) | $200,000 | $2,400,000 |
| With Enterprise | 20 Pro + 5 Enterprise | 30 avg | Mixed | $272,500 | $3,270,000 |

### Assumptions

- Professional tier is the volume driver. Most firms land here.
- Enterprise deals close slower but carry higher ACV and longer contracts.
- Starter serves as a pipeline tier -- firms evaluate at Starter and upgrade to Professional as they add compliance requirements.
- Churn assumption: less than 10% annual (self-hosted platforms have high switching costs).
- Add-on revenue (integrations, HA setup, training) not included in projections but expected to add 15-25% on top of license revenue.

### Revenue Mix Target (Steady State)

| Tier | % of Customers | % of Revenue |
|---|---|---|
| Starter | 40% | 15% |
| Professional | 45% | 50% |
| Enterprise | 15% | 35% |

---

## 7. Discount Programs

### Annual Prepayment Discount

- **15% discount** on the annual total when paid upfront.
- Example: Professional tier, 20 seats = $96,000/year standard. With annual prepay = $81,600/year (saving $14,400).
- Benefit to Quietfire AI: Improved cash flow, reduced churn risk.

### Early Adopter Program (First 10 Customers)

- **25% discount** on tier pricing for the first 12 months.
- Applies to the first 10 paying customers across any tier.
- Example: Professional tier, 20 seats = $8,000/month standard. Early adopter rate = $6,000/month for 12 months.
- After 12 months, pricing reverts to standard tier rate.
- Early adopters receive priority input on the product roadmap.
- Discounts are stackable with annual prepay (25% early adopter + 15% annual = 36.25% effective discount).

### Non-Profit and Legal Aid Discount

- **40% discount** on tier pricing for verified non-profit organizations and legal aid providers.
- Requires 501(c)(3) documentation or equivalent verification.
- No expiration -- discount applies for the life of the contract.
- Example: Professional tier, 10 seats = $4,000/month standard. Non-profit rate = $2,400/month.

### Volume Discount (Enterprise Tier)

- Negotiable for deployments exceeding 100 seats.
- Typical range: 10-20% discount on per-seat pricing.
- Bundled with multi-year commitment (2-3 year terms).

---

## Appendix: Pricing Decision Log

This section tracks pricing decisions and rationale as the model evolves.

| Date | Decision | Rationale |
|---|---|---|
| Feb 2026 | Set Starter at $150/seat | Below Clio's effective per-seat cost; low enough for real estate entry market while still qualifying leads |
| Feb 2026 | Set Professional at $400/seat | Sweet spot for mid-size law firms; compliance value justifies premium over basic practice management tools |
| Feb 2026 | Set Enterprise at $750-1,000/seat | Reflects dedicated engineering time and custom compliance work; competitive with enterprise legal tech |
| Feb 2026 | Minimum seats (5 Starter, 10 Professional) | Filters out single-user evaluations; ensures minimum viable revenue per customer |
| Feb 2026 | No per-API-call pricing | Eliminates adoption friction; firms will not approve unpredictable AI costs |
| Feb 2026 | 25% early adopter discount | Accelerates first 10 customers; builds reference base for larger deals |
| Feb 2026 | 40% non-profit discount | Social impact positioning; legal aid firms become advocates in the legal community |

---

*This is an internal strategy document. Pricing is subject to refinement based on market feedback, competitive dynamics, and early customer conversations. All figures represent list pricing before applicable discounts.*
