import subprocess
import os
import sys
import re

# --- 1. Dual-Logging Setup ---
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
    # --- 2. Path Setup ---
    # Automatically finds the directory where this .py file is saved
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Initialize Logger
    log_file_path = os.path.join(base_path, "final_repair_log.txt")
    sys.stdout = Logger(log_file_path)

    # Define tool paths
    golden_rtl = os.path.normpath(os.path.join(base_path, "golden_rtl", "arith_unit.v"))
    buggy_net = os.path.normpath(os.path.join(base_path, "buggy_netlist", "arith_unit_bug.v"))
    output_dir = os.path.normpath(os.path.join(base_path, "patched_netlist"))
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"--- STARTING ECO REPAIR SESSION ---")
    print(f"[INFO] Project Path: {base_path}")

    # --- 3. Robust Hybrid Instruction ---
    # We provide a strict template to prevent the AI from "chatting" too much
    instruction = (
        f"ACT AS A VLSI ECO AGENT. "
        f"1. Compare Reference: {golden_rtl} and Buggy: {buggy_net}. "
        f"2. Fix the sum bit-slice '&' to '+' and swap the xor_out nibbles. "
        f"3. MANDATORY: Print the fixed Verilog module exactly like this: "
        f"---FIXED_CODE_START--- "
        f"[Full Verilog Module Here] "
        f"---FIXED_CODE_END--- "
    )

    # --- 4. Command Construction (Fixed with Trust Flags) ---
    cmd_list = [
        "codex", "exec", 
        "--full-auto", 
        "--skip-git-repo-check", # Essential for running outside of Git
        f"\"{instruction}\""
    ]
    cmd_string = " ".join(cmd_list)

    try:
        print("[STATUS] Invoking AI Agent for Logic Analysis...")
        # Capture both stdout and stderr
        result = subprocess.run(cmd_string, capture_output=True, text=True, shell=True, encoding='utf-8')
        
        # Display the Raw Output for the Log
        print("\n=== RAW AGENT OUTPUT ===")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"CLI NOTIFICATION/ERROR: {result.stderr}")
        print("========================\n")

        # --- 5. Python-Side Extraction ---
        # Search for markers (Case-Insensitive)
        pattern = r"---FIXED_CODE_START---(.*?)---FIXED_CODE_END---"
        match = re.search(pattern, result.stdout, re.DOTALL | re.IGNORECASE)

        if match:
            fixed_verilog = match.group(1).strip()
            
            # Remove any markdown code fences the AI might have added
            fixed_verilog = fixed_verilog.replace("```verilog", "").replace("```", "").strip()
            
            patch_path = os.path.join(output_dir, "arith_unit_patched.v")
            
            with open(patch_path, "w") as f:
                f.write(fixed_verilog)
            
            print(f"[SUCCESS] Python extracted and saved the patch to: {patch_path}")
            
            # --- 6. Local Verification (Icarus Verilog) ---
            print("[STATUS] Running Icarus Verilog Simulation...")
            testbench = os.path.join(base_path, "tb", "tb_arith_unit.v")
            lib = os.path.join(base_path, "lib", "std_cells.v")
            
            # Construct shell command for Windows
            verify_cmd = f"iverilog -o sim.out \"{testbench}\" \"{patch_path}\" \"{lib}\" && vvp sim.out"
            v_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True)
            
            print("\n=== SIMULATION RESULTS ===")
            if v_result.stdout:
                print(v_result.stdout)
            if v_result.stderr:
                print(f"SIMULATION LOG/ERROR: {v_result.stderr}")
            print("==========================\n")
            
        else:
            print("[ERROR] AI did not provide code markers correctly. Extraction failed.")

    except Exception as e:
        print(f"[FATAL ERROR] {str(e)}")

    print(f"--- SESSION COMPLETE. ALL LOGS SAVED TO {log_file_path} ---")

if __name__ == "__main__":
    start_arith_eco_cycle()