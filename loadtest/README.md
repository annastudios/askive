# Askive load test

**One API pod handles 50 simultaneous heavy users with 0 errors (p95 5.0 s
for a new question, 4.7 s of which is the language model); with autoscaling
to 3 pods, 100 users run at 0.1% errors instead of 11.7%.**

## Method

- **Where:** minikube with 2 CPUs and 2.5 GB, shared by every pod and by the
  load generator. [Locust](https://locust.io) runs as a Job inside the
  cluster and calls the `api` Service directly, so the laptop's network
  isn't part of the measurement.
- **What each simulated user does:** signs up, logs in, uploads a small
  document, then every 1-3 seconds asks a common question (60%, often
  cached), a new question (30%, full search and answer) or lists its
  documents (10%). Users arrive 2 per second.
- **AI calls:** Voyage and Gemini are replaced by timed stand-ins
  (`FAKE_AI=1`, see `app/services/fake_ai.py`): 0.15 s per embedding call
  and 4.5 s per answer, matching latencies measured against the real
  services. The test spends no API quota and measures Askive itself, not
  the AI providers.
- **Measurement:** each step runs for 150 s; statistics are reset once all
  users have arrived, so they describe steady load rather than the sign-up
  burst. We report p95 latency (95% of requests finish within it) and the
  error rate.

## Results

| Simultaneous users | 1 API pod: errors | 1 pod: new question p95 | Autoscaled (3 pods): errors | 3 pods: new question p95 |
| --- | --- | --- | --- | --- |
| 10 | 0% | 4.9 s | 0% | 4.8 s |
| 25 | 0% | 4.8 s | 0% | 6.2 s |
| 50 | 0% | 5.0 s | 0% | 5.5 s |
| 100 | 11.7% (pod restarted) | 29 s | 0.1% | 18 s |

Cached answers return in about 11 ms (median) throughout. At 100 users the
limit is CPU: three pods share minikube's 2 CPUs, so they keep working but
slow down; a real server would have more headroom.

The 1-pod runs used a stricter liveness probe (3 failures of 3 s), which
restarted the saturated pod at 100 users. It was loosened (6 failures of
5 s) before the autoscaled run.

## What it found and fixed

Before these fixes, one pod started failing at 50 users and collapsed at
100. Each run is kept in `results/`:

| Run | Change | New question p95 at 50 users | Errors at 50 users |
| --- | --- | --- | --- |
| `1-one-pod-before-fixes` | starting point | 7.7 s ("list documents": 2.7 s) | 0.7% |
| `2-one-pod-bigger-thread-pool` | 100 worker threads, async liveness | 17 s: the real cause was elsewhere | 0% |
| `3-one-pod-all-fixes` | per-chat keyword index | 5.0 s | 0% |
| `4-autoscaled-1-to-3-pods` | autoscaler on (1 to 3 pods) | 5.5 s | 0% (100 users: 0.1%) |

1. **Keyword index rebuilt on every upload.** BM25 covered every chunk of
   every user and was rebuilt (8.8 s for about 1,900 chunks) whenever the
   chunk count changed. Under load, many requests rebuilt it at once and
   saturated the CPU. Each chat now gets a small index over only its own
   documents, built once and cached.
2. **Liveness probe killed busy pods.** It ran on a worker thread, so it
   timed out when all threads were busy, and Kubernetes restarted a pod that
   was busy, not dead, dropping every request in flight. It's now `async`
   (answered without a thread) and lenient.
3. **Thread pool too small.** Each question holds a worker thread for the
   whole language-model call, so the default of 40 capped a pod at 40
   questions in flight. It's now 100 (`THREAD_POOL_SIZE`).

**Remaining limits:** bcrypt makes sign-up and login deliberately
CPU-heavy (about 0.4 s each) so stolen password hashes are hard to crack,
which makes bursts of sign-ups the most expensive traffic. The autoscaler
scales on CPU, so it can't see time spent waiting on the language model;
fully async AI calls would remove the thread limit altogether.

## Running it

With Askive deployed on minikube (see the main README):

```bash
pip install -r loadtest/requirements.txt
kubectl set env deploy/api -n askive FAKE_AI=1     # never for real users
python loadtest/run_k8s.py --label my-run --users 10 25 50 100 --spawn-rate 2 --duration 150s
kubectl set env deploy/api -n askive FAKE_AI-      # back to the real APIs
```

The script runs each step as a Kubernetes Job, prints a table as it goes
and saves it to `results/<label>.md`. To test 1 pod without autoscaling,
run `kubectl delete hpa api -n askive` and
`kubectl scale deploy/api -n askive --replicas=1` first.

To run Locust against a local server instead, start the API with
`FAKE_AI=1` and run:

```bash
locust -f loadtest/locustfile.py --host http://localhost:8000
```

then open http://localhost:8089 for Locust's live charts.
