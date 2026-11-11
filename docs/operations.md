# Operations and recovery

## Start, stop and update

Use the package launcher or Docker Desktop's Compose project controls. The launchers check the
backend rather than waiting for absent speech models, so a fresh installation can reach setup.
Only the backend is published, on loopback. Keep Docker Desktop running during use.

Before updating, create a backup in Settings and stop the project. Extract a newer release and
start its launcher. Releases pin image digests; application data and models keep the same named
volumes. Database migrations run at backend startup. A schema downgrade is not a general recovery
mechanism: for example, mixed execution plans cannot be downgraded to the earlier short field.

Do not run `docker compose down -v` to update or troubleshoot: that explicitly deletes volumes.
The launchers never delete volumes or prune Docker's unrelated images and caches.

## Storage

| Volume | Contents |
|---|---|
| `probeloop_data` | SQLite database, supplied blobs, session recordings/exports, local configuration and account tokens |
| `probeloop_models` | Speech models, voices, approved ONNX classifier, installer receipts and partial downloads |
| `probeloop_postgres` | Database files when the optional source-deployment PostgreSQL profile is used |

The provisioner is the only long-running writer of the model volume. It verifies approved files
before activation. Consumers mount models read-only. Temporary download parts belong to the
installer; a retry resumes them where supported and revalidates the final complete file. Valid
models are reused rather than copied into application images or per-service volumes.

A verified download completes independently of engine warm-up. Reload notifications are best
effort: a speech worker that is still loading does not turn verified files into a failed download.
It retries model loading automatically; voice remains unavailable until its readiness check passes.

The Laya installer downloads only its int8 ONNX and tokenizer, about 342 MB. The full Safetensors
checkpoint is for maintainers and further training; it is not downloaded by the application.

## Backups, restores and deletion

Settings can export structured data or create a portable ZIP containing SQL rows, owned document
blobs, recordings and session exports. Backups record the schema revision and support SQLite or
PostgreSQL stores. Restoring rebuilds the appropriate schema and applies later migrations.

Portable backups exclude model weights, ChatGPT tokens and machine settings such as tool choices
and installation preferences. Restoring user data does not replace the machine's provider
configuration. **Delete application data** similarly keeps machine settings, installed models
and account configuration. Account sign-out is a separate action.

Backup, restore, deletion and configuration changes are guarded against active interviews and
background jobs. Make the app idle first. Keep backups outside the running data volume and
protect them as personal information; they can contain documents, recordings and transcripts.

## Failures

- **Provider unavailable:** the interview pauses with saved answers and remains pinned to its
  selected tools. Restore the connection or sign-in and resume explicitly.
- **Speech recognition or synthesis problem:** inspect the speech status shown by the app.
  Recognition and synthesis have their own existing delivery/error handling; their failures
  must not be described as an automatic change of LLM provider.
- **Provisioner unavailable:** start the complete runtime, then retry the component from Settings.
- **Interrupted install:** persisted jobs are queued after restart; downloaded files are checked
  and valid ones reused. Incorrect weights remain unavailable.
- **Low disk space:** the model installer refuses a download without room for staging. Free
  space deliberately through Docker Desktop; do not remove unrelated projects automatically.

For source deployments, inspect recent service logs with:

```bash
docker compose logs --tail 100 backend provisioner stt-worker tts-piper
```

Normal logs contain operation identifiers, states and timings, not document text, transcripts
or audio. Debug LLM logs are separate and sensitive. A health endpoint means the process is
available; model and provider readiness are reported separately in the application.
