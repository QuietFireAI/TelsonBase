# TB-PROOF-054 -- Toolroom and Foreman Agent Test Suite

**Sheet ID:** TB-PROOF-054
**Claim Source:** tests/test_toolroom.py
**Status:** VERIFIED
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "720 tests passing" -- README, proof_sheets/INDEX.md

This sheet proves the **Toolroom and Foreman Agent Test Suite**: 129 tests across 28 classes verifying the Toolroom and Foreman agent: tool registry CRUD, trust-level checkout authorization, HITL approval gates, manifest validation, function tool execution, semantic version comparison, and full REST endpoint coverage.

## Verdict

VERIFIED -- All 129 tests pass. The Toolroom correctly gates external tool access by agent trust level. The Foreman agent enforces checkout authorization, triggers HITL approval for API-class tools, validates install sources against the approved-sources allowlist, and manages the tool manifest lifecycle. Function tools execute with authorization checks and return structured results. REST endpoints enforce authentication across all toolroom operations.

## Test Classes

| Class | Tests | Proves |
|---|---|---|
| `TestToolMetadata` | 3 | ToolMetadata construction, defaults, and round-trip serialization |
| `TestToolCheckout` | 2 | ToolCheckout creation and round-trip serialization |
| `TestToolRegistry` | 11 | Register, list, checkout, return, and request tools; active checkout filtering |
| `TestTrustLevelNormalization` | 6 | Accept lowercase, uppercase, mixed-case, and cross-tier trust level strings |
| `TestForemanCheckout` | 5 | Authorize or block checkout by trust level; HITL trigger for API-access tools |
| `TestForemanInstall` | 4 | Reject unapproved sources; create approval for approved sources; validate approval state |
| `TestToolroomStore` | 4 | Store singleton existence, required methods, get_store helper |
| `TestCeleryConfiguration` | 3 | Foreman in Celery include, daily update in beat schedule, task routing |
| `TestToolroomAPI` | 8 | Toolroom status, list tools, get tool, list checkouts, checkout history, list requests, usage report via REST |
| `TestApprovalIntegration` | 2 | Approval rule registration and configuration validation |
| `TestToolroomPostCheckout` | 4 | POST /checkout endpoint authorization and response |
| `TestToolroomPostReturn` | 3 | POST /return endpoint and checkout release |
| `TestToolroomPostInstallPropose` | 4 | POST /install/propose source validation and approval creation |
| `TestToolroomPostInstallExecute` | 2 | POST /install/execute approval enforcement |
| `TestToolroomPostRequest` | 4 | POST /request unapproved tool request flow |
| `TestToolroomPostApiCheckoutComplete` | 3 | POST /checkout/complete HITL API tool completion |
| `TestToolManifest` | 5 | Manifest structure, defaults, round-trip, JSON round-trip, unknown field handling |
| `TestManifestValidation` | 13 | Required fields, shell injection prevention, sandbox level, timeout range, network-without-sandbox warning |
| `TestManifestFileLoading` | 5 | Load from file, handle missing directory, missing manifest file, invalid JSON, invalid manifest |
| `TestFunctionToolRegistry` | 7 | Register, auto-generate manifest, get by name, get nonexistent, list all, unregister, unregister nonexistent |
| `TestRegisterFunctionToolDecorator` | 2 | Decorator registers function with metadata and preserves the callable |
| `TestExecutionResult` | 2 | Success and failure ExecutionResult construction |
| `TestFunctionToolExecution` | 4 | Execute function tool: success, string return, None return, exception isolation |
| `TestApprovalStatusLookup` | 4 | Pending, completed, not found, and dict-format approval status lookup |
| `TestSemanticVersionComparison` | 7 | Newer, v-prefix, same, older, prerelease, v-prefix vs no-prefix, and patch increment |
| `TestToolroomExecuteEndpoint` | 3 | POST /execute auth enforcement, payload validation, no-active-checkout error |
| `TestForemanExecution` | 4 | No-checkout fails, function tool execution, no-manifest fails, sync function tools |
| `TestToolMetadataV460` | 5 | manifest_data field, manifest_data default, execution_type field, execution_type default, round-trip with manifest |

## Source Files Tested

- `tests/test_toolroom.py`
- `toolroom/registry.py` -- ToolMetadata, ToolCheckout, ToolRegistry
- `toolroom/foreman.py` -- Foreman agent, handle_checkout_request, trust-level enforcement
- `toolroom/function_tools.py` -- FunctionToolRegistry, register_function_tool decorator
- `toolroom/manifest.py` -- ToolManifest schema and validation
- `toolroom/executor.py` -- ExecutionResult, function and subprocess execution engine
- `routers/toolroom.py` -- REST endpoints
- `celery_app/worker.py` -- Foreman task routing and beat schedule

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/test_toolroom.py -v --tb=short
```

## Expected Result

```
129 passed
```

---

*Sheet TB-PROOF-054 | ClawCoat v11.0.2 | March 19, 2026*
