import subprocess
import re

def get_pid_by_port(port):
    try:
        result = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True)
        lines = result.decode().splitlines()

        for line in lines:
            parts = re.split(r'\s+', line.strip())
            if len(parts) >= 5 and parts[1].endswith(f":{port}"):
                pid = int(parts[-1])
                return pid
    except subprocess.CalledProcessError:
        print(f"❌ No process found on port {port}")
        return None

def kill_process_windows(pid):
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
        print(f"✅ Process {pid} killed successfully.")
    except subprocess.CalledProcessError:
        print(f"❌ Failed to kill process {pid}.")

# Main
def main(port_to_kill):
    pid = get_pid_by_port(port_to_kill)
    if pid:
        print(f"🔍 Found PID {pid} using port {port_to_kill}")
        kill_process_windows(pid)


if __name__ == "__main__":
    main()