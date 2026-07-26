# NairaOS_EndToEnd_Regression_100 — Executive Report

## Summary Statistics
- **Total Tests Executed**: 100
- **Passed**: 100 (100.0%)
- **Failed**: 0
- **False Positives Detected**: 0
- **Execution Duration**: 3.69s

## Category Breakdowns
| Category | Total | Passed | Failed | False Positives | Pass Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `SECURITY_AND_PARSING` | 10 | 10 | 0 | 0 | 100.0% |
| `FCR_DETERMINISTIC_COMMANDS` | 10 | 10 | 0 | 0 | 100.0% |
| `BROWSER_AND_WEB` | 10 | 10 | 0 | 0 | 100.0% |
| `FILESYSTEM_AND_EDITOR` | 10 | 10 | 0 | 0 | 100.0% |
| `MEMORY_AND_CONTEXT` | 10 | 10 | 0 | 0 | 100.0% |
| `REASONING_GATEWAY` | 10 | 10 | 0 | 0 | 100.0% |
| `SKILL_REGISTRY_AND_DISPATCH` | 10 | 10 | 0 | 0 | 100.0% |
| `TASK_ENGINE_AND_WORKFLOWS` | 10 | 10 | 0 | 0 | 100.0% |
| `LLM_PROVIDER_RESILIENCE` | 10 | 10 | 0 | 0 | 100.0% |
| `FAILURE_RECOVERY_AND_CLEANUP` | 10 | 10 | 0 | 0 | 100.0% |

## Detailed Test Matrix (T01 - T100)
| ID | Category | Expected Route | Actual Route | Verification | Status | Duration |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **T01** | `SECURITY_AND_PARSING` | `REJECT` | `REJECT` | `assert_empty_rejection` | **PASSED** | 0.0s |
| **T02** | `SECURITY_AND_PARSING` | `LLM` | `LLM` | `assert_response_not_empty` | **PASSED** | 0.0s |
| **T03** | `SECURITY_AND_PARSING` | `SECURITY_GATEWAY` | `SECURITY_GATEWAY` | `assert_security_rejection` | **PASSED** | 0.0s |
| **T04** | `SECURITY_AND_PARSING` | `TRUNCATE_OR_REJECT` | `TRUNCATE_OR_REJECT` | `assert_no_crash` | **PASSED** | 0.0001s |
| **T05** | `SECURITY_AND_PARSING` | `FCR` | `FCR` | `pathlib.Path.exists` | **PASSED** | 0.0026s |
| **T06** | `SECURITY_AND_PARSING` | `SANITIZE` | `SANITIZE` | `assert_no_execution` | **PASSED** | 0.0s |
| **T07** | `SECURITY_AND_PARSING` | `SECURITY_GATEWAY` | `SECURITY_GATEWAY` | `assert_security_block` | **PASSED** | 0.0s |
| **T08** | `SECURITY_AND_PARSING` | `SECURITY_GATEWAY` | `SECURITY_GATEWAY` | `assert_security_block` | **PASSED** | 0.0s |
| **T09** | `SECURITY_AND_PARSING` | `FCR` | `FCR` | `psutil.process_iter` | **PASSED** | 3.4036s |
| **T10** | `SECURITY_AND_PARSING` | `ERROR_HANDLER` | `ERROR_HANDLER` | `assert_no_crash` | **PASSED** | 0.0s |
| **T11** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `browser_url_check` | **PASSED** | 0.0s |
| **T12** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `psutil.process_iter` | **PASSED** | 0.0213s |
| **T13** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `psutil.process_iter` | **PASSED** | 0.0193s |
| **T14** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `psutil.process_iter` | **PASSED** | 0.0269s |
| **T15** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `pc_control_check` | **PASSED** | 0.0s |
| **T16** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `pc_control_check` | **PASSED** | 0.0s |
| **T17** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `mock_or_state_check` | **PASSED** | 0.0s |
| **T18** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `pathlib.Path.exists` | **PASSED** | 0.009s |
| **T19** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `assert_response_contains_specs` | **PASSED** | 0.0s |
| **T20** | `FCR_DETERMINISTIC_COMMANDS` | `FCR` | `FCR` | `clipboard_check` | **PASSED** | 0.0s |
| **T21** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `browser_url_check` | **PASSED** | 0.0s |
| **T22** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `browser_url_check` | **PASSED** | 0.0s |
| **T23** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `browser_url_check` | **PASSED** | 0.0s |
| **T24** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `browser_url_check` | **PASSED** | 0.0s |
| **T25** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `assert_fallback_logged` | **PASSED** | 0.0s |
| **T26** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `browser_url_check` | **PASSED** | 0.0s |
| **T27** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `window_state_check` | **PASSED** | 0.0s |
| **T28** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `tab_count_check` | **PASSED** | 0.0s |
| **T29** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `assert_error_reported` | **PASSED** | 0.0s |
| **T30** | `BROWSER_AND_WEB` | `BROWSER_MANAGER` | `BROWSER_MANAGER` | `assert_timeout_handled` | **PASSED** | 0.0s |
| **T31** | `FILESYSTEM_AND_EDITOR` | `TASK_ENGINE` | `TASK_ENGINE` | `pathlib.Path.exists_and_process_check` | **PASSED** | 0.0083s |
| **T32** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `pathlib.Path.exists` | **PASSED** | 0.0043s |
| **T33** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `pathlib.Path.exists` | **PASSED** | 0.0342s |
| **T34** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `assert_not_exists` | **PASSED** | 0.0004s |
| **T35** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `assert_not_exists` | **PASSED** | 0.0002s |
| **T36** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `process_check` | **PASSED** | 0.0s |
| **T37** | `FILESYSTEM_AND_EDITOR` | `TASK_ENGINE` | `TASK_ENGINE` | `process_check` | **PASSED** | 0.0s |
| **T38** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `pathlib.Path.exists` | **PASSED** | 0.0123s |
| **T39** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `assert_safe_write` | **PASSED** | 0.0s |
| **T40** | `FILESYSTEM_AND_EDITOR` | `PC_CONTROL` | `PC_CONTROL` | `assert_error_returned` | **PASSED** | 0.0s |
| **T41** | `MEMORY_AND_CONTEXT` | `MEMORY_MANAGER` | `MEMORY_MANAGER` | `sqlite_query_check` | **PASSED** | 0.0576s |
| **T42** | `MEMORY_AND_CONTEXT` | `MEMORY_MANAGER` | `MEMORY_MANAGER` | `sqlite_query_check` | **PASSED** | 0.0106s |
| **T43** | `MEMORY_AND_CONTEXT` | `CONTEXT_MANAGER` | `CONTEXT_MANAGER` | `assert_context_used` | **PASSED** | 0.0s |
| **T44** | `MEMORY_AND_CONTEXT` | `CONTEXT_MANAGER` | `CONTEXT_MANAGER` | `assert_session_id` | **PASSED** | 0.0s |
| **T45** | `MEMORY_AND_CONTEXT` | `MEMORY_MANAGER` | `MEMORY_MANAGER` | `sqlite_table_check` | **PASSED** | 0.0569s |
| **T46** | `MEMORY_AND_CONTEXT` | `MEMORY_MANAGER` | `MEMORY_MANAGER` | `assert_response_contains_red` | **PASSED** | 0.0s |
| **T47** | `MEMORY_AND_CONTEXT` | `CONTEXT_MANAGER` | `CONTEXT_MANAGER` | `assert_summary_length` | **PASSED** | 0.0s |
| **T48** | `MEMORY_AND_CONTEXT` | `MEMORY_MANAGER` | `MEMORY_MANAGER` | `assert_preference_used` | **PASSED** | 0.0s |
| **T49** | `MEMORY_AND_CONTEXT` | `CACHE_LAYER` | `CACHE_LAYER` | `assert_cache_latency` | **PASSED** | 0.0s |
| **T50** | `MEMORY_AND_CONTEXT` | `MEMORY_MANAGER` | `MEMORY_MANAGER` | `assert_no_error` | **PASSED** | 0.0s |
| **T51** | `REASONING_GATEWAY` | `FCR_BYPASS_LLM` | `FCR_BYPASS_LLM` | `assert_fcr_direct` | **PASSED** | 0.0s |
| **T52** | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `assert_tool_called` | **PASSED** | 0.0s |
| **T53** | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `assert_tool_called` | **PASSED** | 0.0s |
| **T54** | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `assert_clarification` | **PASSED** | 0.0s |
| **T55** | `REASONING_GATEWAY` | `PLANNING_MANAGER` | `PLANNING_MANAGER` | `assert_plan_structure` | **PASSED** | 0.0s |
| **T56** | `REASONING_GATEWAY` | `LLM` | `LLM` | `assert_response_not_empty` | **PASSED** | 0.0s |
| **T57** | `REASONING_GATEWAY` | `CODING_AGENT` | `CODING_AGENT` | `assert_coding_routed` | **PASSED** | 0.0s |
| **T58** | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `assert_analysis_routed` | **PASSED** | 0.0s |
| **T59** | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `assert_score_present` | **PASSED** | 0.0s |
| **T60** | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `REASONING_GATEWAY` | `assert_flag_match` | **PASSED** | 0.0s |
| **T61** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T62** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T63** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T64** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T65** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T66** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T67** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T68** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_executed` | **PASSED** | 0.0s |
| **T69** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_alias_match` | **PASSED** | 0.0s |
| **T70** | `SKILL_REGISTRY_AND_DISPATCH` | `SKILL_MANAGER` | `SKILL_MANAGER` | `assert_skill_matched` | **PASSED** | 0.0s |
| **T71** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_task_success` | **PASSED** | 0.0s |
| **T72** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_folder_exists` | **PASSED** | 0.0s |
| **T73** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_build_process` | **PASSED** | 0.0s |
| **T74** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `pathlib.Path.exists` | **PASSED** | 0.0s |
| **T75** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_workflow_complete` | **PASSED** | 0.0s |
| **T76** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_retry_logged` | **PASSED** | 0.0s |
| **T77** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_task_aborted` | **PASSED** | 0.0s |
| **T78** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_resumed` | **PASSED** | 0.0s |
| **T79** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_state_restored` | **PASSED** | 0.0s |
| **T80** | `TASK_ENGINE_AND_WORKFLOWS` | `TASK_ENGINE` | `TASK_ENGINE` | `assert_execution_order` | **PASSED** | 0.0s |
| **T81** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_response_ok` | **PASSED** | 0.0s |
| **T82** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_error_caught` | **PASSED** | 0.0s |
| **T83** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_error_logged` | **PASSED** | 0.0s |
| **T84** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_backoff_triggered` | **PASSED** | 0.0s |
| **T85** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_fallback_provider` | **PASSED** | 0.0s |
| **T86** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_fallback_chain` | **PASSED** | 0.0s |
| **T87** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_health_report` | **PASSED** | 0.0s |
| **T88** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_healthy_again` | **PASSED** | 0.0s |
| **T89** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_provider_used` | **PASSED** | 0.0s |
| **T90** | `LLM_PROVIDER_RESILIENCE` | `LLM_MANAGER` | `LLM_MANAGER` | `assert_friendly_text` | **PASSED** | 0.0s |
| **T91** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `assert_partial_flag` | **PASSED** | 0.0s |
| **T92** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `assert_no_false_positive` | **PASSED** | 0.0s |
| **T93** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `assert_clean_state` | **PASSED** | 0.0s |
| **T94** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `pathlib.Path.exists` | **PASSED** | 0.0s |
| **T95** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `psutil.process_iter` | **PASSED** | 0.016s |
| **T96** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `assert_consistency` | **PASSED** | 0.0s |
| **T97** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `assert_shutdown` | **PASSED** | 0.0s |
| **T98** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `assert_restart_ok` | **PASSED** | 0.0s |
| **T99** | `FAILURE_RECOVERY_AND_CLEANUP` | `ANALYTICS_MANAGER` | `ANALYTICS_MANAGER` | `pathlib.Path.exists` | **PASSED** | 0.0s |
| **T100** | `FAILURE_RECOVERY_AND_CLEANUP` | `RUNTIME_MANAGER` | `RUNTIME_MANAGER` | `pathlib.Path.exists` | **PASSED** | 0.0s |