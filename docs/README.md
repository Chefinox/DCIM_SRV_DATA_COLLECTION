# Documentation Directory

Comprehensive documentation for DCIM Metrics Project.

## Structure

### architecture/
System architecture and design documentation:
- **19-kafka-pipeline-architecture.md** - Complete pipeline architecture (v3.5)
- **24-versioning-change-management-standard.md** - FIT041 compliance, version history
- **32-final-architecture-v3.4.md** - Final v3.4 architecture with diagrams
- **35-pipeline-version-comparison.md** - v3.4 vs v4.0 comparison
- **36-complete-pipeline-diagram.md** - Latest end-to-end diagram (v3.4.1)

### operations/
Operational reports and incident documentation:
- **23-mt014-recovery-report.md** - MT014 recovery incident
- **26-dcim-maintenance-sync-report.md** - Maintenance sync report
- **28-bmc-lockout-incident.md** - BMC lockout incident analysis

### development/
Development guides, metrics documentation, and technical references:
- Metrics documentation (servers, UPS, NAS, network, CCTV)
- Data collection methods
- Telegraf configuration guides
- PostgreSQL query references
- Ralph integration guides
- Dashboard templates (*.ndjson)
- MIB guides (*.pdf)

### raw_data/
Raw device data samples for reference:
- SNMP walks (*.txt)
- Redfish responses (*.json)
- Metric inventories (*.csv)
- MIB files (*.mib)

## Key Documents

### Getting Started
1. Read `architecture/36-complete-pipeline-diagram.md` for current architecture
2. Check `architecture/24-versioning-change-management-standard.md` for version history
3. Review `operations/` for known issues and resolutions

### For Developers
1. `development/` contains technical guides and metrics documentation
2. `raw_data/` has sample data for testing and validation
3. Architecture docs explain design decisions

### For Operations
1. `operations/` has incident reports and maintenance procedures
2. Architecture docs explain system behavior
3. Development docs have troubleshooting guides

## Document Naming Convention

- **##-descriptive-name.md** - Numbered documents (chronological)
- **descriptive-name.md** - General documentation
- **metrics_*.md** - Metrics documentation by device type
- **raw_*.txt** - Raw device data samples

## Updates

Documentation is updated with each significant change. Check git history for detailed changelog:
```bash
git log --oneline docs/
```
