---
name: git_review
description: Use this when the user wants to check their recent amrvac changes, review a git diff, or commit their code to the repository.
---
# Git Diff Review and Commit Workflow

1. Run `git status` using the `run_command` tool to check which physics files have been modified in the amrvac directory.
2. Run `git diff` to view the exact line-by-line code changes. 
3. Review the code changes:
   * Ensure there are clear comments explaining any new physics equations or numerical solvers.
   * Check that no temporary debug lines or print statements were left behind.
4. If everything looks good, ask the user for permission to stage the changes using `git add`.
5. Write a clean, professional conventional-commit message in the format: `type(scope): short description` (e.g., `feat(solver): update boundary conditions for amrvac simulation`).
6. Present the proposed commit message to the user, and execute `git commit -m "your message"` only after they explicitly approve it.