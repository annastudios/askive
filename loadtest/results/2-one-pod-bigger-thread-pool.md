## 1 pod, bigger thread pool only

100 worker threads + async liveness (3x 3s); global BM25 index still rebuilt on every upload. Users arrive 10/s, 120 s per step. FAKE_AI=1 (0.15 s embeddings, 4.5 s answers), minikube 2 CPUs. Stats reset after all users arrived.

| Users | API pods | Request | req/s | p50 ms | p95 ms | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 1 | chat: common question | 1.2 | 11 | 5100 | 0.0% |
| 10 | 1 | chat: new question | 0.6 | 4700 | 4700 | 0.0% |
| 10 | 1 | documents: list | 0.2 | 11 | 18 | 0.0% |
| 10 | 1 | Aggregated | 2.2 | 4500 | 5600 | 0.0% |
<!-- 10 users: CACHE chat: common question: 92/138 answers cached (67%) -->
<!-- 10 users: CACHE chat: new question: 0/68 answers cached (0%) -->
| 25 | 1 | chat: common question | 2.7 | 11 | 4500 | 0.0% |
| 25 | 1 | chat: new question | 1.4 | 4700 | 4700 | 0.0% |
| 25 | 1 | documents: list | 0.3 | 12 | 22 | 0.0% |
| 25 | 1 | Aggregated | 5.1 | 4500 | 8100 | 0.0% |
<!-- 25 users: CACHE chat: common question: 199/318 answers cached (63%) -->
<!-- 25 users: CACHE chat: new question: 0/168 answers cached (0%) -->
| 50 | 1 | chat: common question | 3.8 | 34 | 16000 | 0.0% |
| 50 | 1 | chat: new question | 1.7 | 4700 | 17000 | 0.0% |
| 50 | 1 | documents: list | 0.6 | 12 | 120 | 0.0% |
| 50 | 1 | Aggregated | 7.3 | 4600 | 19000 | 0.0% |
<!-- 50 users: CACHE chat: common question: 239/434 answers cached (55%) -->
<!-- 50 users: CACHE chat: new question: 0/192 answers cached (0%) -->
| 100 | 1 | chat: common question | 1.1 | 4500 | 7700 | 4.3% |
| 100 | 1 | chat: new question | 0.6 | 4700 | 13000 | 8.2% |
| 100 | 1 | documents: list | 0.2 | 12 | 11000 | 10.5% |
| 100 | 1 | Aggregated | 4.0 | 4700 | 38000 | 23.0% |
<!-- 100 users: CACHE chat: common question: 37/112 answers cached (33%) -->
<!-- 100 users: CACHE chat: new question: 0/56 answers cached (0%) -->
