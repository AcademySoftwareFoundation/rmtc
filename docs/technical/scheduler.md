# Scheduler 

Scheduler defines the shared abstractions (Scheduler, Task, Job, Executor, Tracker) used by Train's scheduling of runs. RMTC Core provides a local implementation on top of this; a facility/render-farm scale wall scheduler (e.g. OpenCue, Deadline) is still outstanding and would extend the same base classes.

When an inference or training operation is executed:
- A scheduler starts a task (infer or train) and kicks off one or more jobs
- A job executes a portion of a task through an executor created from the task
- Once the executor is finished the results are merged into the task (in order)
- The task is updated
- Once all jobs are complete the task is marked finished

Executors exist to abstract the actual call function of each to permit abstraction. Results are merged in immediately to avoid issues loss if a job was to fail.

Tasks report the number of executions it needs to perform (>=1) and the number of executions it has completed. An executor can execute all or some of the executions.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
