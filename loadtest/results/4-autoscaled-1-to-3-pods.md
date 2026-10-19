## Autoscaled, 1 to 3 pods

All fixes, HPA at 70% CPU, lenient liveness (6x 5s). Users arrive 2/s, 150 s per step. FAKE_AI=1 (0.15 s embeddings, 4.5 s answers), minikube 2 CPUs. Stats reset after all users arrived.

| Users | API pods | Request | req/s | p50 ms | p95 ms | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 1 | chat: common question | 1.4 | 11 | 4600 | 0.0% |
| 10 | 1 | chat: new question | 0.7 | 4700 | 4800 | 0.0% |
| 10 | 1 | documents: list | 0.3 | 11 | 22 | 0.0% |
| 10 | 1 | Aggregated | 2.5 | 58 | 4700 | 0.0% |
<!-- 10 users: CACHE chat: common question: 148/197 answers cached (75%) -->
<!-- 10 users: CACHE chat: new question: 0/106 answers cached (0%) -->
| 25 | 3 | chat: common question | 3.3 | 16 | 4800 | 0.0% |
| 25 | 3 | chat: new question | 1.7 | 4700 | 6200 | 0.0% |
| 25 | 3 | documents: list | 0.5 | 15 | 130 | 0.0% |
| 25 | 3 | Aggregated | 5.9 | 1200 | 5600 | 0.0% |
<!-- 25 users: CACHE chat: common question: 336/459 answers cached (73%) -->
<!-- 25 users: CACHE chat: new question: 0/233 answers cached (0%) -->
| 50 | 3 | chat: common question | 6.5 | 11 | 4600 | 0.0% |
| 50 | 3 | chat: new question | 3.0 | 4700 | 5500 | 0.0% |
| 50 | 3 | documents: list | 0.9 | 10 | 22 | 0.0% |
| 50 | 3 | Aggregated | 11.2 | 4300 | 6200 | 0.0% |
<!-- 50 users: CACHE chat: common question: 567/806 answers cached (70%) -->
<!-- 50 users: CACHE chat: new question: 0/368 answers cached (0%) -->
| 100 | 3 | chat: common question | 2.7 | 4500 | 15000 | 0.0% |
| 100 | 3 | chat: new question | 1.3 | 4700 | 18000 | 0.3% |
| 100 | 3 | documents: list | 0.4 | 11 | 9700 | 0.0% |
| 100 | 3 | Aggregated | 5.0 | 4500 | 21000 | 0.1% |
<!-- 100 users: CACHE chat: common question: 375/772 answers cached (49%) -->
<!-- 100 users: CACHE chat: new question: 0/371 answers cached (0%) -->
