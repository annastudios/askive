## 1 pod, all fixes

Per-chat cached BM25 index, 100 threads, async liveness (3x 3s). Users arrive 2/s, 150 s per step. FAKE_AI=1 (0.15 s embeddings, 4.5 s answers), minikube 2 CPUs. Stats reset after all users arrived.

| Users | API pods | Request | req/s | p50 ms | p95 ms | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 1 | chat: common question | 1.5 | 12 | 4500 | 0.0% |
| 10 | 1 | chat: new question | 0.7 | 4700 | 4900 | 0.0% |
| 10 | 1 | documents: list | 0.3 | 12 | 44 | 0.0% |
| 10 | 1 | Aggregated | 2.6 | 15 | 4700 | 0.0% |
<!-- 10 users: CACHE chat: common question: 169/217 answers cached (78%) -->
<!-- 10 users: CACHE chat: new question: 0/94 answers cached (0%) -->
| 25 | 1 | chat: common question | 3.5 | 11 | 4500 | 0.0% |
| 25 | 1 | chat: new question | 1.7 | 4700 | 4800 | 0.0% |
| 25 | 1 | documents: list | 0.5 | 10 | 17 | 0.0% |
| 25 | 1 | Aggregated | 6.1 | 27 | 4800 | 0.0% |
<!-- 25 users: CACHE chat: common question: 361/483 answers cached (75%) -->
<!-- 25 users: CACHE chat: new question: 0/232 answers cached (0%) -->
| 50 | 1 | chat: common question | 6.0 | 11 | 4500 | 0.0% |
| 50 | 1 | chat: new question | 2.9 | 4700 | 5000 | 0.0% |
| 50 | 1 | documents: list | 1.1 | 10 | 19 | 0.0% |
| 50 | 1 | Aggregated | 10.8 | 4500 | 10000 | 0.0% |
<!-- 50 users: CACHE chat: common question: 517/753 answers cached (69%) -->
<!-- 50 users: CACHE chat: new question: 0/371 answers cached (0%) -->
| 100 | 1 | chat: common question | 3.4 | 4500 | 25000 | 4.7% |
| 100 | 1 | chat: new question | 1.6 | 4700 | 29000 | 3.9% |
| 100 | 1 | documents: list | 0.5 | 14 | 27000 | 6.0% |
| 100 | 1 | Aggregated | 7.0 | 4500 | 36000 | 11.7% |
<!-- 100 users: CACHE chat: common question: 161/339 answers cached (47%) -->
<!-- 100 users: CACHE chat: new question: 0/157 answers cached (0%) -->
