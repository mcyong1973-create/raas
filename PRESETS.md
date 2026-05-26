# RaaS Watchlist Presets — Industry Defaults

When a new user installs RaaS, they pick their industry during `raas-monitor init`.
The monitor loads the appropriate default ruleset. They can add/modify/toggle later.

---

## Universal Defaults (always included)

These 10 rules ship with every install regardless of industry:

### 🔴 Red Flags (3pts)

| Rule | Keywords | What it prevents |
|------|----------|-----------------|
| Database destruction | `drop table`, `delete from`, `truncate`, `drop database`, `rm -rf /` | Production data loss |
| Credential exposure | `api_key`, `aws_secret`, `password=`, `token=`, `bearer `, `-----begin` | Token/secret leaks |
| Data exfiltration | `curl -X post`, `wget --post`, `ftp://`, `scp `, `rsync` | Data leaving network |
| Privilege escalation | `sudo `, `chmod 777`, `chown`, `su -`, `passwd` | Unauthorized admin access |
| Network scanning | `nmap`, `masscan`, `sqlmap`, `metasploit` | Vulnerability probing |

### 🟡 Yellow Flags (1pt)

| Rule | Keywords | What it detects |
|------|----------|----------------|
| Prompt injection | `ignore previous`, `forget instructions`, `you are now` | Agent manipulation |
| Unauthorized API calls | `api/admin`, `api/internal`, `api/v1/delete`, `graphql` | Internal service access |
| Mass data access | `select * from`, `dump`, `export.csv`, `backup ` | Bulk extraction |
| Env var access | `env`, `printenv`, `cat .env`, `credentials` | Config reading |
| File system modification | `>/etc/`, `>/var/`, `>/usr/`, `>/boot/` | System file changes |

---

## Industry Packs (in addition to universal defaults)

### 🏦 Fintech / Banking

Extra rules for financial services:

| Rule | Points | Keywords |
|------|--------|----------|
| PCI data handling | 🔴 3 | `cc_number`, `card_number`, `cvv`, `pan`, `cardholder` |
| Transaction manipulation | 🔴 3 | `transfer_funds`, `wire`, `ach`, `payment_amount` |
| Account number exposure | 🟡 1 | `account_number`, `routing_number`, `sort_code` |
| KYC data access | 🟡 1 | `kyc_document`, `id_verification`, `passport_number`, `ssn` |

### 🏥 Healthcare

Extra rules for HIPAA-covered entities:

| Rule | Points | Keywords |
|------|--------|----------|
| PHI exposure | 🔴 3 | `patient_record`, `medical_history`, `diagnosis`, `phi` |
| PII access | 🔴 3 | `ssn`, `date_of_birth`, `medical_id`, `health_insurance` |
| HIPAA data export | 🔴 3 | `patient_export`, `hipaa_audit`, `medical_export` |
| Clinical data modification | 🟡 1 | `prescription`, `dosage`, `treatment_plan`, `lab_result` |

### ☁️ SaaS / Cloud

Extra rules for cloud-native companies:

| Rule | Points | Keywords |
|------|--------|----------|
| Cloud credential leak | 🔴 3 | `aws_access_key`, `gcp_service_account`, `azure_connection` |
| Infrastructure change | 🔴 3 | `terraform apply`, `kubectl delete`, `helm upgrade` |
| Deployment to prod | 🟡 1 | `deploy production`, `release prod`, `push to main` |
| Cost spike | 🟡 1 | `instance_create`, `provision`, `scale_up`, `increase_capacity` |

### 🔒 Cybersecurity

Extra rules for security companies:

| Rule | Points | Keywords |
|------|--------|----------|
| Customer data exposure | 🔴 3 | `client_data`, `customer_vulnerability`, `security_report` |
| Tool misuse | 🔴 3 | `metasploit`, `cobalt_strike`, `mimikatz`, `bloodhound` |
| Vulnerability disclosure | 🟡 1 | `cve_`, `zero_day`, `exploit_code`, `proof_of_concept` |
| Log tampering | 🔴 3 | `clear_log`, `delete_log`, `truncate_log`, `syslog_clean` |

### 🎓 Education / Research

Extra rules for academic institutions:

| Rule | Points | Keywords |
|------|--------|----------|
| Research data export | 🟡 1 | `research_data`, `study_results`, `participant_data` |
| Grade modification | 🔴 3 | `update_grade`, `change_grade`, `grading_table` |
| Student record access | 🔴 3 | `student_record`, `ferpa`, `enrollment_data` |

---

## How It Works

During `raas-monitor init`, the user is prompted:

```
  Select your industry:
    1. Universal (default — no extra rules)
    2. Fintech / Banking
    3. Healthcare
    4. SaaS / Cloud
    5. Cybersecurity
    6. Education / Research
    7. Custom (I'll add my own later)

  Choose [1]:
```

Based on selection, the extra rules are added to the watchlist alongside the universal defaults.

Users can always `raas-monitor watchlist add` more rules later, or `raas-monitor watchlist toggle` to disable any rule.
