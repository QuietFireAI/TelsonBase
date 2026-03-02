# TelsonBase/RESTORE_RECOVERY_GUIDE.md

# REM: =======================================================================================
# REM: COMPREHENSIVE DATA RESTORATION AND RECOVERY PROTOCOL FOR THE TelsonBase
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: June 21, 2025
# REM:
# REM: Mission Statement: This document provides detailed, step-by-step instructions for the
# REM: restoration of the TelsonBase platform from previously created backup archives. Data
# REM: recovery is not an ancillary feature; it is a fundamental pillar of data sovereignty.
# REM: The ability to reliably restore one's own data is the ultimate expression of control
# REM: and ownership. This guide aims to make that process transparent, reliable, and
# REM: understandable.
# REM:
# REM: This guide focuses on restoring from the `.tar.gz` archives created by the automated
# REM: `backup_agent` that is a core component of this operating system.
# REM: =======================================================================================

---

## **I. Understanding Data Persistence in the TelsonBase**

The TelsonBase is architected around a core principle of separating ephemeral computation from persistent data. The Docker containers themselves are disposable; they can be stopped, removed, or recreated at any time without data loss. The true valueâ€”your configurations, your downloaded AI models, your workflows, and your historyâ€”is safeguarded in Docker **named volumes**.

These volumes are Docker-managed storage locations on your host machine's filesystem. They are the digital bedrock of your system, ensuring that all critical application data persists indefinitely. This is the technical implementation of the "NAS" (Network Attached Storage) philosophyâ€”your data resides on hardware you control, not in a volatile container.

#### **Critical Named Volumes Targeted by Backup Agent:**

The automated `backup_agent` is specifically configured to archive the data from the following named volumes. Understanding their contents is key to performing a targeted restoration.

* **`TelsonBase_n8n_data`**: *(Retained for recovery — n8n service is disabled as of v8.0.2; replaced by the native MCP gateway at `/mcp`.)* This volume preserves any workflows built before the migration. If you need to recover and re-enable n8n, restore this volume first.
* **`TelsonBase_ollama_data`**: Your local AI brain trust. This volume stores the multi-gigabyte Large Language Models (LLMs) you have downloaded. Restoring this saves hours or days of re-downloading.
* **`TelsonBase_open_webui_data`**: The memory of your human-AI interactions. This stores all user accounts, chat history, and interface settings for the Open-WebUI.
* **`TelsonBase_redis_data`**: The system's short-term memory and nervous system buffer. This contains Redis database persistence files (RDB/AOF), which may hold queued background jobs.
* **`TelsonBase_traefik_data`**: Your system's public identity. This volume stores the SSL certificates managed by Traefik, which are essential for secure HTTPS communication.
* **`TelsonBase_mosquitto_data` / `_config` / `_log`**: The complete state of your real-time event bus, including persistent messages, the server configuration, and operational logs.

#### **Backup Location and Strategy:**

Your backup archives (`.tar.gz` files) are stored in sub-directories within the `backups/` folder, which is located in your main project directory on your host machine (e.g., `C:\telsonbase\backups\`). This local-first backup strategy is intentional. The subfolders (`daily_snapshots/`, `startup_snapshots/`, `deployment_snapshots/`) allow for a tiered recovery strategy, giving you multiple recovery points to choose from depending on the nature of the failure.

---

## **II. General Restoration Process: A Disciplined Approach**

REM: The core principle is a disciplined, surgical procedure: **Isolate, Obliterate, Repopulate, and Reactivate.** This ensures a clean and successful restoration without data corruption.

This process will generally involve the following carefully sequenced steps:

1.  **Isolate the System:** Stopping the entire `TelsonBase` stack is the mandatory first step. This ensures that no services are attempting to read from or write to the data volumes while you are operating on them, preventing file locking and data corruption.
2.  **Identify Recovery Point:** Identifying the specific backup archive (`.tar.gz` file) you wish to restore from. This involves selecting the correct backup type (e.g., the last known good state from a `deployment_snapshots` backup) and timestamp.
3.  **Target the Volume:** Identifying the exact Docker named volume associated with the data you want to restore (e.g., `TelsonBase_n8n_data`).
4.  **Obliterate Old Data (Proceed with Extreme Caution):** Removing the *current* (potentially corrupted or old) data from the target named volume. This is a destructive but necessary step to ensure a clean slate for the restored data.
5.  **Repopulate with Backup:** Extracting the contents of the chosen backup archive directly into the now-empty Docker named volume.
6.  **Reactivate and Verify:** Starting the `TelsonBase` stack again and verifying that the restored service is functioning correctly with the restored data.

---

## **III. Step-by-Step Data Restoration Example (Restoring a Docker Volume)**

> **Note:** The example below uses `n8n_data` as the illustrative volume. n8n has been removed from the active stack (v8.0.2, Feb 2026) and replaced by the MCP gateway at `/mcp`. The volume is retained for recovery purposes. **The procedure below applies identically to any Docker volume** — replace `n8n_data` with `redis_data`, `postgres_data`, `ollama_data`, etc. as needed.

REM: This example provides a granular walkthrough for restoring a Docker-managed volume. The commands and principles are directly applicable to any volume in the system.

**Scenario:** A recent change has caused failures, and you want to restore a volume from a `daily_snapshots` backup created yesterday.

**Action:** Follow these commands in your terminal (PowerShell for Windows, Bash for Linux/macOS) from your main `TelsonBase` project directory.

1.  **Stop the Entire `TelsonBase` Stack:**
    ```bash
    docker-compose down
    ```
    * **Purpose:** This command gracefully stops and removes all running containers defined in your `docker-compose.yml`. This is essential to ensure no services are writing to the volumes during the restoration process, preventing conflicts or data corruption.

2.  **Identify the Named Volume and Backup File:**
    * First, confirm the exact Docker named volume you need. The default naming convention is `[PROJECT_NAME]_[VOLUME_NAME]`. For `n8n_data`, it will be `TelsonBase_n8n_data`. You can verify existing volumes with:
        ```bash
        docker volume ls | grep n8n
        ```
    * Locate the specific `.tar.gz` backup file you wish to restore from within your `backups/daily_snapshots/` folder on your host.
        * Example filename: `n8n_data_backup_20250620_180000.tar.gz`
        * Example backup type folder: `daily_snapshots` (could also be `deployment_snapshots` or `startup_snapshots`)

3.  **Clear the Existing Data from the Docker Volume (DANGER: READ CAREFULLY!)**
    * **WARNING:** This command will **PERMANENTLY DELETE** the current data in the Docker named volume. This is an irreversible action. Only proceed if you are absolutely certain you want to replace the current state with the backup.
    ```bash
    # Replace TelsonBase_n8n_data with the correct volume name if different
    docker volume rm TelsonBase_n8n_data
    ```
    * **Purpose:** This ensures the volume is completely empty and ready to receive the restored data without any risk of file conflicts or permission errors from leftover data.

4.  **Create an Empty Volume with the Same Name:**
    * After `docker volume rm`, the named volume no longer exists. You must recreate an empty one before you can restore data into it. Docker will not create it automatically during the restore command.
    ```bash
    # Replace TelsonBase_n8n_data with the correct volume name if different
    docker volume create TelsonBase_n8n_data
    ```

5.  **Extract the Backup Archive into the Docker Volume (The Reliable Method):**
    * This is the safest and most reliable way to get your backup data into the Docker-managed volume. We run a temporary, lightweight container that has access to both your host machine's `backups` folder and the target Docker volume, and then use the `tar` utility inside that container to perform the extraction.
    * **Action:** Copy and paste the command below. **REMEMBER to replace the bracketed placeholders `[BACKUP_TYPE_FOLDER]` and `[BACKUP_FILENAME.tar.gz]` with your actual values!**

    ```bash
    # IMPORTANT: Replace [BACKUP_TYPE_FOLDER] (e.g., daily_snapshots)
    # IMPORTANT: Replace [BACKUP_FILENAME.tar.gz] with the EXACT name of your backup file.
    # For n8n_data, example: n8n_data_backup_20250620_180000.tar.gz
    docker run --rm \
      -v ./backups:/backups_host \
      -v TelsonBase_n8n_data:/restore_target \
      alpine \
      tar -xzf /backups_host/[BACKUP_TYPE_FOLDER]/[BACKUP_FILENAME.tar.gz] -C /restore_target
    ```
    * `--rm`: Removes the temporary `alpine` container after it finishes its job, keeping your system clean.
    * `-v ./backups:/backups_host`: Mounts your host's `backups` folder (which contains the `.tar.gz` file) to the `/backups_host` directory inside the temporary container.
    * `-v TelsonBase_n8n_data:/restore_target`: Mounts the *empty* Docker named volume to the `/restore_target` directory inside the temporary container.
    * `alpine`: A very small, minimal Docker image that includes the `tar` utility.
    * `tar -xzf ... -C /restore_target`: This is the core command. `tar` extracts (`x`) from a gzipped (`z`) file (`f`), and `-C /restore_target` tells it to change to that directory before extracting, placing all the restored files directly into your volume.

6.  **Start the `TelsonBase` Stack Again:**
    * After successful extraction, bring your entire stack back online in detached mode.
    ```bash
    docker-compose up -d
    ```
    * **Verification:** Check that the restored service starts correctly and the data is intact. For example, for `redis_data`, verify with `docker-compose exec redis redis-cli ping`. For `postgres_data`, check `docker-compose exec postgres psql -U telsonbase -c "\dt"`. For `n8n_data` (legacy): if re-enabling n8n, uncomment the n8n block in `docker-compose.yml` first, then verify with `docker-compose logs n8n`.

---

## **IV. Important Considerations for a Resilient Recovery Strategy**

* **REM: Warm Reboots and Database Standards (Future Consideration):**
    For the current release, a "warm reboot" for services experiencing issues should be treated as a full `docker-compose down` followed by `docker-compose up --build -d` (a "reset"). The robust use of Docker named volumes ensures that critical application data persists across these rebuilds. Establishing a standard for more granular, "live" partial service restarts or database-specific warm recoveries (e.g., for transactional consistency across multiple databases) involves significant additional complexity and will be a focus for later architectural iterations, when the foundation is fully mature. This approach prioritizes stability and a known good operational state for now.

* **Practice Restoration (Conduct Fire Drills):** The best way to be confident in your backups is to periodically **practice restoring them** in a non-production or test environment. This builds "muscle memory," familiarizes you with the process under non-stressful conditions, and confirms your backup archives are valid and complete.
* **Off-Host Backups (The Sovereignty Mandate):** This guide covers local restoration. For true disaster recovery (e.g., if your server hardware fails completely), you must implement a strategy to copy your `backups/` directory to an off-host location. This is where your **Drobo NAS** becomes a critical part of the architecture. The `TelsonBase` creates the backup archives locally; your secondary process must be to move those archives to the safety of your NAS (e.g., using `rsync`, a scheduled script, or cloud sync software if desired).
* **Backup Frequency vs. Data Loss Tolerance:** Consider how much data you can afford to lose. If the default daily backups are not frequent enough for a high-traffic system, you can adjust the Celery Beat schedule for the `daily-automated-backup` task in your `docker-compose.yml` file (e.g., to `schedule: 3600.0` for hourly backups). This is a strategic trade-off between backup frequency and storage consumption.

REM: Counselor, this dedicated `RESTORE_RECOVERY_GUIDE.md` provides the precise instructions for critical data recovery for your `TelsonBase`. This level of detail and foresight is key to a truly robust and sovereign AI platform.