# Scoped angr Symbolic Execution for Stripped PIE Binaries

> Preserved from Google Drive draft (`1. Symbolic Execution (angr ／ REMaQE TODO)

  Wha....docx`).

---

Here is the exact angr implementation to bridge that gap, bypassing the 105MB CFG overhead, handling the stripped environment, and extracting the algebraic offset.

1. Bypassing CFG and Scoping the Execution

For a 105MB stripped PIE binary, do not use proj.analyses.CFG(). Instead, dictate the base address manually to align with your Ghidra/IDA offsets, disable library loading, and use a call_state or blank_state to restrict the engine entirely to your target block.

Python

import angrimport claripy# Force a base address of 0x0 so PIE offsets match your static analysis tools perfectlyproj = angr.Project('lina_9.14.2.14',                     main_opts={'base_addr': 0x0},                     load_options={'auto_load_libs': False})start_addr = 0x1184232end_addr = 0x1184500 # Replace with the actual block exit address# Inject a symbolic pointer to track the structgp_obj_ptr = claripy.BVS('gp_obj', 64)# Create a state starting exactly at the init function# Assuming the struct pointer is passed via the first argument (RDI in x64 sysv)state = proj.factory.call_state(start_addr, gp_obj_ptr)

2. Stubbing Stripped Calls (SimProcedures)

If 0x1184232 calls other internal functions or missing libc imports, angr will get lost in unmapped memory or suffer state explosion. You must hook these calls manually using SimProcedures or simple Python hooks.

Python

# Scenario A: Stubbing a known libc call in a stripped binary# If you know 0x1185000 is malloc, hook it with angr's built-in SimProcedureproj.hook(0x1185000, angr.SIM_PROCEDURES['libc']['malloc']())# Scenario B: NOP-ing an irrelevant internal function to save state@proj.hook(0x1184280, length=5) # length of the call instructiondef skip_irrelevant_call(state):    # Do nothing, just return immediately to skip the call overhead    pass

3. Execution and Algebraic Extraction

Run the simulation manager just for this basic block or function. Once the find condition is met, use claripy to extract the AST (Abstract Syntax Tree) representing the symbolic offset computation.

Python

simgr = proj.factory.simgr(state)# Explore strictly between the start and end of your init blocksimgr.explore(find=end_addr)if simgr.found:    target_state = simgr.found[0]        # Assuming you want to see what was written to gp_obj->offset (e.g., at RDI + 0x48)    # Read 8 bytes from the symbolic pointer + offset    extracted_val = target_state.memory.load(gp_obj_ptr + 0x48, 8)        # Print the algebraic expression (the AST)    print("Offset AST:", extracted_val)        # If it resolves to a concrete mathematical formula, simplify it:    simplified_ast = target_state.solver.simplify(extracted_val)    print("Simplified:", simplified_ast)else:    print("Failed to reach end of init block. Check simgr.deadended or simgr.errored.")

Key Execution Constraints to Prevent Explosion:

Memory alignment: If the struct fields must be initialized to specific values to avoid branching errors during the init block, use state.add_constraints() before running simgr.explore().

Instruction limit: If the block is strictly linear, you can use simgr.step(num_inst=50) instead of explore() to forcefully constrain how far angr can wander.
