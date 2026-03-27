import os
import subprocess
import sys
import shutil

def check_command(cmd, name):
    print(f"Checking {name}...", end=" ")
    path = shutil.which(cmd)
    if path:
        print(f"OK ({path})")
        return True
    else:
        print("MISSING")
        return False

def check_python_version():
    print(f"Checking Python version...", end=" ")
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 12:
        print(f"OK ({sys.version})")
        return True
    else:
        print(f"FAILED (found {sys.version}, need 3.12+)")
        return False

def check_ollama():
    print("Checking Ollama service...", end=" ")
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            print("OK (Running)")
            return True
        else:
            print(f"FAILED (Status {response.status_code})")
            return False
    except Exception:
        print("OFFLINE (Could not connect to http://localhost:11434)")
        return False

def check_network():
    print("Checking network connectivity (google.com)...", end=" ")
    try:
        import httpx
        response = httpx.get("https://google.com", timeout=3.0)
        if response.status_code == 200:
            print("OK (Online)")
            return True
        else:
            print(f"LIMITED (Status {response.status_code})")
            return True # Not strictly a failure for local-only
    except Exception:
        print("OFFLINE (Air-gapped mode)")
        return True # Expected in some local environments

def main():
    print("=== DeerFlow Local Diagnostic Tool ===\n")
    success = True
    
    # Core tools
    success &= check_python_version()
    success &= check_command("uv", "uv (Python package manager)")
    success &= check_command("node", "Node.js")
    success &= check_command("pnpm", "pnpm (Node package manager)")
    success &= check_command("docker", "Docker")
    success &= check_command("nginx", "Nginx")
    
    # Service checks
    print("\nChecking for running services...")
    success &= check_ollama()
    
    try:
        # Check if Docker is running
        subprocess.run(["docker", "ps"], capture_output=True, check=True)
        print("Docker Daemon: Running")
    except:
        print("Docker Daemon: Not Running or Access Denied")
        # success = False # Don't fail if docker is missing but we want local mode

    # Connectivity check
    print("")
    check_network()

    if success:
        print("\nAll core local dependencies found!")
    else:
        print("\nSome dependencies are missing. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
