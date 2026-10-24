# Bug report: a background job in a Claude Code cloud session was killed when the turn ended, and the session came back in plan mode

**Product:** Claude Code on the web (cloud session, Anthropic-hosted container)
**Session:** https://claude.ai/code/session_01QQfLbNLxSyJ2LR7dQoeh7R
**Date:** 2026-10-24 (all times UTC)

## What I was doing

I approved a plan for an unattended overnight job: a batch of about 280 optimizer runs, expected to take 6–7 hours
on the container's 4 CPUs. I told Claude I'd be away for about 15 hours. Claude:

- started the batch as background processes (`nohup`), with a watchdog script that restarts the runner if it stops;
- scheduled a one-shot check-in through the session's own scheduler (`send_later`, 60 minutes later) to resume the
  work after a container restart;
- ended its turn at about 01:07.

## What happened

| Time (UTC) | Event |
|---|---|
| ~00:55 | Batch and watchdog start in the background. |
| ~01:07 | Claude's turn ends. The batch is still running. |
| 01:09:03 | Last write by the batch (its log and a result file). Nothing after this. |
| 02:04 | The scheduled check-in fires and wakes the session. |
| 02:05 | `uptime` shows the container booted seconds earlier. The batch, the watchdog and every other process are gone. 14 of 283 jobs had finished. |
| 02:05 | The session came back with **plan mode active** ("The user indicated that they do not want you to execute yet"), although the plan had been approved and was mid-execution. Claude could only look, not relaunch the batch, so it stayed stopped. |
| ~19:10 (next session start) | I returned. The 15 hours had passed with about 15 minutes of real work done. |

Separately, "This session's worker process was restarted" appeared several times during the day, and the GitHub and
other MCP servers repeatedly disconnected and reconnected.

## Expected

- Background processes started in a session keep running after the turn ends, at least for a documented minimum
  time, or the session tells me at the time that they won't.
- Or, if the container is reclaimed, a scheduled wake-up can resume the work. In particular, the session's
  permission mode after a restart is the one it had before (here: an approved plan, executing), not plan mode.

## Actual

- The container was reclaimed (or stopped) a couple of minutes after the turn ended, killing the background job
  even though it was using all CPUs. Nothing said this would happen.
- When the scheduled check-in restarted the session, it came back in plan mode, which blocked the exact action the
  check-in was scheduled for. The run was lost for the night.

## Impact

An overnight unattended job (the main use I had for leaving the session) did ~15 minutes of a ~7-hour workload.
Workaround: run the batch on my own computer instead.

## Suggestions

1. Document how long background processes survive after a turn ends in a cloud session, and warn when a session
   ends a turn with processes still running in the background.
2. Keep a container alive while it has busy background processes (or offer an explicit "keep running" option).
3. Restore the previous permission mode when a session restarts or is woken by a scheduled task; don't fall back
   to plan mode for work the user has already approved.
