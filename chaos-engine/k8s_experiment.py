
import subprocess
import time
import sys

CONTEXT = "kind-chaospilot"
NAMESPACE = "default"
DEPLOYMENT = "recommendationservice"
EXPERIMENT_DURATION = 10


def kubectl(*args):
    command = [
        "kubectl",
        "--context", CONTEXT,
        "--namespace", NAMESPACE,
        *args
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=True
    )

    return result.stdout.strip()


def get_replicas():
    return int(
        kubectl(
            "get", "deployment", DEPLOYMENT,
            "-o", "jsonpath={.spec.replicas}"
        )
    )


def restore(replicas):
    print(f"Restoring {DEPLOYMENT} to {replicas} replicas...")

    kubectl(
        "scale", "deployment", DEPLOYMENT,
        f"--replicas={replicas}"
    )

    kubectl(
        "rollout", "status",
        f"deployment/{DEPLOYMENT}",
        "--timeout=180s"
    )

    print("Service restored successfully!")


def main():
    current_context = subprocess.check_output(
        ["kubectl", "config", "current-context"],
        text=True
    ).strip()

    if current_context != CONTEXT:
        sys.exit(
            f"Wrong Kubernetes context: {current_context}"
        )

    original_replicas = get_replicas()

    if original_replicas < 1:
        sys.exit("Service is already scaled down!")

    print(f"Original replicas: {original_replicas}")

    
    try:
        print("Injecting failure...")
        kubectl(
            "scale", "deployment", DEPLOYMENT,
            "--replicas=0"
        )

        print("Waiting for pods to terminate...")
        kubectl(
            "wait",
            "--for=delete",
            "pod",
            "-l", "app=recommendationservice",
            "--timeout=30s"
        )

        print("Failure active for 10 seconds...")
        time.sleep(EXPERIMENT_DURATION)

    finally:
        restore(original_replicas)



if __name__ == "__main__":
    main()
