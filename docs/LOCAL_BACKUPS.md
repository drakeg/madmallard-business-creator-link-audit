# Backup, Recovery & Data Retention Policy

## Overview

This document covers manual operator procedures for SQLite database backups, off-device storage, replacement-stack recovery exercises, and documented RPO/RTO targets. No automated schedules or cloud resources are created by default.

**Important:** These procedures are for a standalone local app running Docker Desktop on macOS. They do not constitute an enterprise-grade disaster-recovery service.

---

## Quick Reference Commands

### Create Backup (Local Volume)
```sh
docker compose exec web python manage.py backup_database
# Output: JSON with snapshot path, SHA256, size, integrity status, row counts
```

### Verify Backup Snapshot
```sh
docker compose exec web python manage.py verify_backup --input /data/backups/audit-TIMESTAMP.sqlite3
# Restores to temp DB, checks integrity/foreign keys/table counts, reopens restored file
```

### Copy to Off-Device Storage (macOS host)
```sh
mkdir -p ~/madmallard-backups  # Or any secure location outside Docker volumes
chmod 700 ~/madmallard-backups
docker compose cp web:/data/backups/audit-TIMESTAMP.sqlite3 \
    ~/madmallard-backups/audit-TIMESTAMP.sqlite3
chmod 600 ~/madmillard-backups/audit-TIMESTAMP.sqlite3
```

### Restore from Backup (Replacement Stack)
See [Recovery Procedure](#recovery-procedure) below for the full replacement-stack workflow.

---

## RPO/RTO Targets (Documented)

| Metric | Target | Notes |
|--------|--------|-------|
| **RPO** (Recovery Point Objective) | ≤ 24 hours | Manual backups are created on-demand; maximum gap between backups is operator-dependent. For production, implement scheduled backups to meet stricter RPO requirements. |
| **RTO** (Recovery Time Objective) | ≤ 4 hours (local stack rebuild) | Assumes: verified backup available, Docker Desktop running, same hardware/OS version. Does not include off-device transfer time or data validation. |
| **Data Loss Window** | Variable | Determined by backup frequency. Default: operator creates backups before major changes or weekly. |

### RPO/RTO Improvement Recommendations

To improve RPO/RTO for production use:
1. Implement scheduled cron jobs to create hourly/daily backups
2. Store backups in multiple locations (local + off-device + cloud)
3. Test recovery procedures quarterly with realistic data volumes
4. Document and validate RPO/RTO targets before customer deployment

---

## Backup Procedures

### Creating a Backup

1. **Create backup snapshot:**
   ```sh
   docker compose exec web python manage.py backup_database --output /data/backups/audit-$(date +%Y%m%d-%H%M%S).sqlite3
   ```

2. **Verify the backup immediately:**
   ```sh
   docker compose exec web python manage.py verify_backup \
     --input /data/backups/audit-TIMESTAMP.sqlite3
   ```

3. **Copy to off-device storage (recommended):**
   ```sh
   mkdir -p ~/madmallard-backups
   chmod 700 ~/madmallard-backups
   docker compose cp web:/data/backups/audit-*.sqlite3 \
       ~/madmillard-backups/
   chmod 600 ~/madmillard-backups/*.sqlite3
   ```

4. **Record backup metadata:**
   - Date/time of backup
   - SHA256 hash (printed by backup command)
   - Row counts for critical tables (also printed)
   - Storage location(s)

### Backup File Security

- Backup files are created with `mode 600` (owner read/write only)
- Password hashes and submitted content are included in backups
- **Do not commit** backup files to Git or share publicly
- Keep `.env` file separate from database snapshots (SECRET_KEY is not in the DB)

---

## Recovery Procedure (Replacement Stack)

### Prerequisites

- Verified backup file available (local or off-device copy)
- Docker Desktop installed and running
- Same OS version recommended (macOS 27.x tested)
- Original `.env` file with correct `DB_PATH` setting

### Step-by-Step Recovery

#### 1. Prepare the Environment

```sh
# Stop existing stack if running
docker compose down

# Create fresh data volume for recovery
rm -rf audit-data  # Only if you want to replace everything

# Start fresh stack (will use backup as new live DB)
docker compose up -d --build
```

#### 2. Restore Backup into Fresh Stack

```sh
# Stop the web service
docker compose exec web python manage.py migrate --noinput

# Copy backup into container's data volume
docker compose cp \
    ~/madmillard-backups/audit-20261117-143022.sqlite3 \
    web:/data/backups/recovery-source.sqlite3

# Restore using Django backup restore command (if available) or manual copy:
docker compose exec web python manage.py shell <<'EOF'
import sqlite3, shutil, os
from pathlib import Path

backup_path = '/data/backups/recovery-source.sqlite3'
live_path = '/data/audit.sqlite3'

# Backup live DB first (in case recovery fails)
shutil.copy(live_path, '/data/live-before-recovery.sqlite3')

# Replace with backup
shutil.copy(backup_path, live_path)
print(f"Recovery complete. New row counts:")
conn = sqlite3.connect(live_path)
cursor = conn.cursor()
for table in ['Customer', 'Project', 'Source', 'Scan', 'Result']:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'  {table}: {cursor.fetchone()[0]} rows')
conn.close()
EOF

# Verify the recovery
docker compose exec web python manage.py verify_backup \
    --input /data/audit.sqlite3
```

#### 3. Validate Recovery

Run these checks to confirm successful recovery:

```sh
# Check sign-in works
curl -X POST http://localhost:8000/login/ \
  -d "username=admin&password=your_admin_password" | grep -i success

# Verify customer scoping (if multi-customer setup)
docker compose exec web python manage.py shell <<'EOF'
from audit.models import Customer, Project
customers = Customer.objects.all()
for c in customers:
    print(f"{c.name}: {c.members.count()} members, {Project.objects.filter(customer=c).count()} projects")
EOF

# Verify reports accessible
curl http://localhost:8000/reports/1/ | grep -i "Link audit report"
```

#### 4. Post-Recovery Actions

- [ ] Confirm all customer data is intact
- [ ] Verify admin can access all projects and reports
- [ ] Check that scan history is preserved
- [ ] Validate discount code register (if applicable)
- [ ] Update backup metadata with new row counts
- [ ] Create a fresh backup after recovery completes

---

## Data Retention & Export Policy

### Retention Guidelines

| Data Type | Recommended Retention | Notes |
|-----------|----------------------|-------|
| Database snapshots | 30 days minimum, 90 days recommended | Keep recent backups for quick recovery |
| Full archive backups | 1 year or longer | For compliance and long-term recovery |
| Exported reports | Indefinite (customer data) | Reports contain customer content; respect privacy policies |
| Scan evidence | As long as project is active | Required for retest comparison workflows |

### Data Export Procedures

#### Export Customer Data (for migration or archival)

```sh
# Export all projects with full scan history to CSV
docker compose exec web python manage.py shell <<'EOF'
from audit.models import Project, Source, Scan, Result, DiscountCode
import csv, io

output = io.StringIO()
writer = csv.writer(output)
writer.writerow(['Project', 'Customer', 'Source Title', 'Scan ID', 'Result Category'])

for project in Project.objects.select_related('customer').all():
    for source in Source.objects.filter(project=project):
        for scan in Scan.objects.filter(project=project).order_by('-created')[:1]:  # Latest scan per source
            for result in Result.objects.filter(scan=scan)[:1]:  # First result per link
                writer.writerow([
                    project.name,
                    project.customer.name,
                    source.title[:50],
                    scan.pk,
                    result.category or 'N/A'
                ])

with open('/data/backups/project-export.csv', 'w') as f:
    f.write(output.getvalue())
print("Export complete: /data/backups/project-export.csv")
EOF
```

#### Export Individual Project Report (HTML)

Use the built-in export feature from the web UI:
1. Navigate to project → scan report
2. Click "Printable HTML" button
3. Save as PDF or HTML file for archival

### Data Deletion Procedures

**Warning:** Deleting data is permanent and cannot be undone without a backup.

#### Delete Specific Scan History

```sh
# From web UI: Project → Delete history (select scans to delete)
# Or via CLI:
docker compose exec web python manage.py shell <<'EOF'
from audit.models import Scan, Result
scans_to_delete = [123, 456]  # Replace with actual scan IDs
for scan_id in scans_to_delete:
    scan = Scan.objects.get(pk=scan_id)
    print(f"Deleting scan {scan.pk} ({scan.project.name})")
    Result.objects.filter(scan=scan).delete()
    scan.delete()
print("Deletion complete.")
EOF
```

#### Delete All Project Data (Nuclear Option)

```sh
# ⚠️ WARNING: This deletes all data in the database!
docker compose exec web python manage.py shell <<'EOF'
from audit.models import Customer, Project, Source, Link, Scan, Result, LoginAttempt, YouTubePreview, DiscountCode
print("Deleting ALL data...")
Customer.objects.all().delete()
Project.objects.all().delete()
Source.objects.all().delete()
Link.objects.all().delete()
Scan.objects.all().delete()
Result.objects.all().delete()
LoginAttempt.objects.all().delete()
YouTubePreview.objects.all().delete()
DiscountCode.objects.all().delete()
print("All data deleted. Database is now empty.")
EOF
```

---

## Off-Device Backup Best Practices

### Recommended Storage Locations

1. **External USB drive** - Physical separation from host machine
2. **Cloud storage (encrypted)** - AWS S3, Google Drive, Dropbox with encryption
3. **Network attached storage (NAS)** - For multi-machine setups
4. **Air-gapped storage** - Maximum security for sensitive data

### Off-Device Backup Schedule

```sh
# Create a backup script for automated off-device backups
cat > ~/madmillard-backup.sh <<'SCRIPT'
#!/bin/bash
set -e

BACKUP_DIR="$HOME/madmillard-backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DATE_TAG=$(date +%Y%m%d)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR/$DATE_TAG"

# Create and verify backup
docker compose exec web python manage.py backup_database \
    --output "/data/backups/audit-${TIMESTAMP}.sqlite3" | tee /tmp/backup-metadata.json

# Copy to off-device storage
docker compose cp "web:/data/backups/audit-${TIMESTAMP}.sqlite3" \
    "$BACKUP_DIR/$DATE_TAG/"

# Set secure permissions
chmod 600 "$BACKUP_DIR/$DATE_TAG/*.sqlite3"

echo "Backup complete: $BACKUP_DIR/$DATE_TAG/"
SCRIPT

chmod +x ~/madmillard-backup.sh
```

### Restore from Off-Device Backup

```sh
# Stop existing stack
docker compose down

# Copy backup into container
docker compose cp \
    ~/madmillard-backups/20261117/audit-20261117-143022.sqlite3 \
    web:/data/backups/recovery-source.sqlite3

# Restore (see Recovery Procedure above)
docker compose exec web python manage.py shell <<'EOF'
import sqlite3, shutil
from pathlib import Path

backup_path = '/data/backups/recovery-source.sqlite3'
live_path = '/data/audit.sqlite3'
shutil.copy(backup_path, live_path)
print("Recovery complete.")
EOF

# Verify and restart
docker compose up -d
```

---

## Disaster Recovery Checklist

Use this checklist before declaring a disaster recovery event:

- [ ] Identify the failure mode (corrupt DB, lost disk, accidental deletion)
- [ ] Locate the most recent verified backup
- [ ] Document current state (row counts, scan states, customer data integrity)
- [ ] Create backup of current database (even if corrupt) for forensics
- [ ] Prepare replacement stack (Docker Desktop, `.env`, dependencies)
- [ ] Execute recovery procedure from this document
- [ ] Validate all critical functionality (sign-in, reports, exports)
- [ ] Notify stakeholders of recovery completion and any data loss
- [ ] Create fresh backup after recovery
- [ ] Update RPO/RTO documentation with actual recovery metrics

---

## Testing & Validation

### Quarterly Recovery Drill (Recommended)

1. **Schedule:** Every 3 months or before major releases
2. **Procedure:**
   - Create a test Docker stack on separate volume
   - Copy latest backup into test stack
   - Validate all features work correctly
   - Document recovery time and any issues
   - Update RPO/RTO targets based on actual performance

### Backup Integrity Verification

```sh
# Verify backup integrity before storing
docker compose exec web python manage.py verify_backup \
    --input /data/backups/audit-20261117-143022.sqlite3

# Expected output:
# - SQLite integrity check: OK
# - Foreign key constraints: Valid
# - Required tables present: All found
# - Row counts match expected values
```

---

## Compliance & Legal Considerations

### Data Privacy

- Database backups contain customer-submitted content and account data
- Ensure compliance with applicable privacy laws (GDPR, CCPA, etc.)
- Document retention periods in legal agreements
- Provide customers ability to request data export/deletion

### Audit Trail

Maintain records of:
- Backup creation timestamps
- Recovery events and procedures used
- Data deletion requests and approvals
- Access logs for backup storage locations

---

## Limitations & Disclaimers

**This documentation does not claim:**

- Automated disaster-recovery service capabilities
- Specific RPO/RTO guarantees without scheduled backups
- Protection against physical hardware failure (use off-device storage)
- Encryption at rest (implement separately if required)
- Multi-site or geographic redundancy

**For production deployments with customer data:**

1. Implement automated backup schedules
2. Store backups in multiple locations (3-2-1 rule: 3 copies, 2 media types, 1 offsite)
3. Test recovery procedures regularly
4. Document and validate RPO/RTO targets before deployment
5. Consult with legal/compliance teams for data retention requirements

---

## Related Documentation

- [TESTING.md](./TESTING.md) - Verification record and test coverage
- [BACKLOG.md](./BACKLOG.md) - Sprint backlog and priorities
- Docker Compose setup in `compose.yml`
- Database schema in `audit/models.py`

<EOF>