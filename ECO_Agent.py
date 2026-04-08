import subprocess
import os
import sys

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        pass

def start_arith_eco_cycle():
    # 1. Path Setup - Targeting the Downloads folder
    # This finds your Windows Downloads folder automatically
    user_profile = os.environ['USERPROFILE']
    base_path = os.path.join(user_profile, "Downloads", "Auto_VLSI")
    
    # Ensure the project folder exists in Downloads
    if not os.path.exists(base_path):
        print(f"[ERROR] Folder not found at {base_path}")
        print("Please move your 'Auto_VLSI' folder to your Downloads folder first.")
        return

    log_file_path = os.path.join(base_path, "repair_session_log.txt")
    sys.stdout = Logger(log_file_path)

    golden_rtl = os.path.normpath(os.path.join(base_path, "golden_rtl", "arith_unit.v"))
    buggy_net = os.path.normpath(os.path.join(base_path, "buggy_netlist", "arith_unit_bug.v"))
    testbench = os.path.normpath(os.path.join(base_path, "tb", "tb_arith_unit.v"))
    output_dir = os.path.normpath(os.path.join(base_path, "patched_netlist"))
    lib_file = os.path.normpath(os.path.join(base_path, "lib", "std_cells.v")) 

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"[INFO] Initializing Arithmetic Unit ECO Cycle...")
    print(f"[INFO] Working Directory: {base_path}")

    # 2. Hardened Instruction - Forcing a direct file write
    instruction = (
        f"TASK: Perform an ECO repair. "
        f"1. Read the buggy file at \"{buggy_net}\". "
        f"2. Apply these fixes: In 'xor_out', swap indices so [7:4] and [3:0] are mapped correctly. In 'sum', change '&' to '+'. "
        f"3. DIRECTIVE: Create the file \"{output_dir}\\arith_unit_patched.v\" and write the full corrected Verilog code into it. "
        f"4. VERIFY: Run 'iverilog -o sim.out \"{testbench}\" \"{output_dir}\\arith_unit_patched.v\" \"{lib_file}\"' "
        f"and then run 'vvp sim.out'. Report the simulation results."
    )

    cmd_list = [
        "codex", "exec", 
        "--full-auto", 
        "--skip-git-repo-check",
        "--sandbox", "none",  # Using 'none' to allow the agent to write to your disk
        f"\"{instruction}\""
    ]
    
    cmd_string = " ".join(cmd_list)

    process = None
    try:
        print("[STATUS] Running repair cycle...")
        process = subprocess.Popen(
            cmd_string, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if process.stdout:
            for line in process.stdout:
                print(f"[AGENT] {line.strip()}")
            
        process.wait()
        
        # 3. Final Verification check
        import time
        time.sleep(1) # Give the OS a second to index the new file
        expected_file = os.path.join(output_dir, "arith_unit_patched.v")
        
        print("-" * 60)
        if os.path.exists(expected_file):
            print(f"[SUCCESS] Patched netlist found at: {expected_file}")
        else:
            print(f"[ERROR] Agent failed to write to disk. Check permissions for: {output_dir}")
        print("-" * 60)

    except Exception as e:
        print(f"[FATAL] Orchestrator Error: {str(e)}")
    finally:
        if process and process.stdout:
            process.stdout.close()

if __name__ == "__main__":
    start_arith_eco_cycle()