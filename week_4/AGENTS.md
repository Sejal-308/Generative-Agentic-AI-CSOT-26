# Code Scout Standing Instructions: amrvac

## 1. System & Project Context
- **Target Repository**: amrvac (MPI-AMRVAC)
- **Primary Languages**: Fortran / Python 
- **Goal**: Locate bugs using grep/definition tools, and safely execute fixes. Summarize instruction and information files and make any necesaary updates as directed by the user. 

## 2. Agent Preferences & Guardrails
- **Read-Only Explore Mode**: Use the "Explore" subagent strategy to gather context first before initiating modifications. Do not pollute the main execution history with excessive raw file text.
- **Tool Discipline**: Use precise arguments when invoking `grep`, `read_file`, or command execution.

## 3. Edit-and-Verify Cycle
- Always follow the strict cycle: Make a change -> Run verification/tests -> Read failures -> Iterate.
- Do not assume a fix works until the verification command proves it.

## 4. Execution Safety Gate
- Any destructive or modification command requires explicit user approval via the safety gate. Read-only commands can run immediately.