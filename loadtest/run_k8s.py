"""
Runs the Locust load test inside the Kubernetes cluster, one step per user
count, and prints/saves a results table.

Locust runs as a Job in the askive namespace and talks to the `api` Service
directly, so the laptop's network isn't part of the measurement. Statistics
are reset once all users are spawned (--reset-stats), so the numbers describe
steady load, not the sign-up burst at the start.

Usage (API must be running with FAKE_AI=1, see README "Load test"):
    python loadtest/run_k8s.py --label one-pod --users 10 25 50 100
"""

import argparse
import csv
import io
import json
import pathlib
import subprocess
import sys

NAMESPACE = "askive"
IMAGE = "locustio/locust:2.46.7"   # keep in step with the locust version used locally
HERE = pathlib.Path(__file__).parent


def kubectl(*args: str, input: str | None = None, check: bool = True) -> str:
    result = subprocess.run(["kubectl", "-n", NAMESPACE, *args], input=input, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.exit(f"kubectl {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def job_manifest(name: str, users: int, spawn_rate: int, duration: str) -> str:
    locust = (
        f"locust -f /mnt/locustfile.py --headless --host http://api "
        f"-u {users} -r {spawn_rate} -t {duration} --reset-stats --only-summary --csv /tmp/r"
    )
    return json.dumps({
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "namespace": NAMESPACE},
        "spec": {
            "backoffLimit": 0,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "locust",
                        "image": IMAGE,
                        "command": ["sh", "-c", f"{locust} 2>&1; echo ===CSV===; cat /tmp/r_stats.csv"],
                        "resources": {"requests": {"cpu": "200m", "memory": "128Mi"}},
                        "volumeMounts": [{"name": "locustfile", "mountPath": "/mnt"}],
                    }],
                    "volumes": [{"name": "locustfile", "configMap": {"name": "locustfile"}}],
                }
            },
        },
    })


def run_step(users: int, spawn_rate: int, duration: str) -> dict:
    name = f"loadtest-{users}"
    kubectl("delete", "job", name, "--ignore-not-found", "--wait=true")
    kubectl("apply", "-f", "-", input=job_manifest(name, users, spawn_rate, duration))
    kubectl("wait", "--for=condition=complete", f"job/{name}", "--timeout=900s")
    logs = kubectl("logs", f"job/{name}")
    replicas = kubectl("get", "deploy", "api", "-o", "jsonpath={.status.replicas}")
    kubectl("delete", "job", name, "--wait=false")

    summary, _, raw_csv = logs.partition("===CSV===")
    rows = {r["Name"]: r for r in csv.DictReader(io.StringIO(raw_csv.strip()))}
    cache_lines = [line for line in summary.splitlines() if line.startswith("CACHE ")]
    return {"users": users, "rows": rows, "api_pods": replicas, "cache": cache_lines}


def row(r: dict, name: str) -> dict:
    s = r["rows"].get(name, {})
    count = int(s.get("Request Count", 0) or 0)
    failures = int(s.get("Failure Count", 0) or 0)
    return {
        "req/s": f"{float(s.get('Requests/s', 0) or 0):.1f}",
        "p50 ms": s.get("50%", "-"),
        "p95 ms": s.get("95%", "-"),
        "errors": f"{100 * failures / count:.1f}%" if count else "-",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="name for this run, e.g. one-pod or autoscaled")
    parser.add_argument("--users", type=int, nargs="+", default=[10, 25, 50, 100])
    parser.add_argument("--spawn-rate", type=int, default=10)
    parser.add_argument("--duration", default="90s", help="per step, including spawning")
    args = parser.parse_args()

    # The locustfile reaches the Job through a ConfigMap.
    configmap = subprocess.run(
        ["kubectl", "-n", NAMESPACE, "create", "configmap", "locustfile",
         f"--from-file=locustfile.py={HERE / 'locustfile.py'}", "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    ).stdout
    kubectl("apply", "-f", "-", input=configmap)

    names = ["chat: common question", "chat: new question", "documents: list", "Aggregated"]
    lines = [
        f"## {args.label}",
        "",
        "| Users | API pods | Request | req/s | p50 ms | p95 ms | Errors |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for users in args.users:
        print(f"running {users} users for {args.duration} ...", flush=True)
        result = run_step(users, args.spawn_rate, args.duration)
        for name in names:
            s = row(result, name)
            lines.append(f"| {users} | {result['api_pods']} | {name} | {s['req/s']} | {s['p50 ms']} | {s['p95 ms']} | {s['errors']} |")
        lines.extend(f"<!-- {users} users: {c} -->" for c in result["cache"])
        print("\n".join(lines[-len(names) - len(result['cache']):]), flush=True)

    out = HERE / "results" / f"{args.label}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
