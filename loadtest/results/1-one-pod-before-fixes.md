## 1 pod, before fixes

40 worker threads, global BM25 index, sync liveness probe (3x 1s), users arrive 10/s, 120 s per step. FAKE_AI=1 (0.15 s embeddings, 4.5 s answers), minikube 2 CPUs. Stats reset after all users arrived.

| Users | API pods | Request | req/s | p50 ms | p95 ms | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 1 | chat: common question | 1.3 | 9 | 4500 | 0.0% |
| 10 | 1 | chat: new question | 0.7 | 4700 | 4700 | 0.0% |
| 10 | 1 | documents: list | 0.3 | 7 | 30 | 0.0% |
| 10 | 1 | Aggregated | 2.5 | 1100 | 4700 | 0.0% |
<!-- 10 users: CACHE chat: common question: 103/150 answers cached (69%) -->
<!-- 10 users: CACHE chat: new question: 0/81 answers cached (0%) -->
| 25 | 1 | chat: common question | 2.9 | 7 | 4600 | 0.0% |
| 25 | 1 | chat: new question | 1.5 | 4700 | 4700 | 0.0% |
| 25 | 1 | documents: list | 0.7 | 6 | 11 | 0.0% |
| 25 | 1 | Aggregated | 5.8 | 3100 | 5800 | 0.0% |
<!-- 25 users: CACHE chat: common question: 225/342 answers cached (66%) -->
<!-- 25 users: CACHE chat: new question: 0/175 answers cached (0%) -->
| 50 | 1 | chat: common question | 4.7 | 9 | 6600 | 0.9% |
| 50 | 1 | chat: new question | 2.4 | 4700 | 7700 | 0.7% |
| 50 | 1 | documents: list | 0.6 | 6 | 2700 | 0.0% |
| 50 | 1 | Aggregated | 8.9 | 4500 | 13000 | 0.7% |
<!-- 50 users: CACHE chat: common question: 310/537 answers cached (58%) -->
<!-- 50 users: CACHE chat: new question: 0/271 answers cached (0%) -->
| 100 | 1 | chat: common question | 1.9 | 4500 | 6600 | 3.3% |
| 100 | 1 | chat: new question | 0.9 | 4700 | 5600 | 4.0% |
| 100 | 1 | documents: list | 0.3 | 6 | 86 | 0.0% |
| 100 | 1 | Aggregated | 5.5 | 4700 | 35000 | 12.7% |
<!-- 100 users: CACHE chat: common question: 87/205 answers cached (42%) -->
<!-- 100 users: CACHE chat: new question: 0/98 answers cached (0%) -->
