# Muse deployment handoff

Copy the complete contents of [MUSE_PROMPT.md](../MUSE_PROMPT.md) into Muse and
provide the complete repository or current release archive alongside it. The
prompt is in English and directs Muse to begin deployment, load the Skill,
configure native reminders, and run live acceptance.

For a private GitHub repository, Muse needs authorized repository access or an
attached source archive. The prompt alone does not contain the implementation.
Do not paste GitHub credentials into chat.

Deployment procedures are in [DEPLOYMENT.md](DEPLOYMENT.md), the native tool
protocol is in [CRON_BRIDGE.md](../references/CRON_BRIDGE.md), and the required
live checks are in [ACCEPTANCE.md](ACCEPTANCE.md). Preserve existing installation
data when repeating deployment. Only real Muse evidence establishes native
readiness.
