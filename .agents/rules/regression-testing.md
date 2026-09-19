---
trigger: always_on
---

# Regression Testing

After modifying Python source code in this repository, verify the change with the automated test suite.

Run:

pytest

If tests fail:

- Inspect the failing test and determine whether the current change caused the regression.
- Fix the implementation when the failure is within the scope of the current task.
- Rerun pytest after the fix.
- Do not modify or weaken an existing test merely to make it pass unless the requested application behavior has intentionally changed.

Before reporting a coding task as complete:

- Run the full pytest suite.
- Confirm that all regression tests pass.
- Report the final test result, including the number of tests passed and failed.

Tests are the authority for previously established behavior. Do not declare a change successful when the regression suite is failing.