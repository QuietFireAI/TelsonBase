# Qualified Message Standard (QMS) — Specification Reference

## Version: 2.1.6 | Protocol: AI Audit Chain

**Architect:** Jeff Phillips — Quietfire AI
**Canonical Reference:** qms.codes  
**License:** Open Standard (MIT)

---

## 1. Guiding Philosophy

QMS exists to solve a single problem: inter-agent AI communication is opaque.

The prevailing paradigm — JSON payloads, implicit API conventions, nested data structures — is efficient for machines but obscures intent and outcome from human oversight. In regulated industries (healthcare, legal, finance), "the computer did it" is not an acceptable answer when automated decisions have real-world consequences.

QMS is built on one radical principle:

> **A log file should be a story, not just a data dump.**

The protocol re-imagines the log file as the primary user interface for system auditability. It serves two audiences simultaneously:

- **For machines:** A simple, robust, unambiguous grammar that standardizes communication, eliminates parsing ambiguity, and makes inter-agent interactions efficient, verifiable, and compliant with standards like the Model Context Protocol (MCP).

- **For humans:** A "human-centric alphabet" — intentionally designed so that a non-technical person (a lawyer, doctor, executive, or student) can read a QMS log file and understand the "code" of an AI conversation without a technical translator or special library.

The protocol's structure *is* the documentation. Its clarity is its strength.

### 1.1 The Secondary Security Layer

QMS is also a **governance primitive** and a **security watermark**.

Cryptographic signatures answer: **who sent this?** (identity)  
QMS formatting answers: **did this come through a legitimate pathway?** (provenance)

These are independent security questions. An attacker who steals an agent's signing key can forge identity. But if they inject raw commands without QMS chain formatting, the system flags the anomaly before the payload executes. The attacker would need to compromise credentials AND reverse-engineer internal message semantics — two independent knowledge barriers.

Think of it like radio comms in a large hotel. Every staff member has a radio with a callsign. If a command comes through without a callsign, or the callsign doesn't match a registered agent — the message is suspect regardless of what it says. No radio, no trust.

This is defense in depth that costs almost nothing at runtime (string formatting and a regex check).

---

## 2. Core Components

### 2.1 The Block — Atomic Unit

A Block is the fundamental, atomic unit of QMS. It is a self-contained, machine-parsable piece of information.

**Syntax:**

```
::CONTENT::
```

**Rules:**

- Every Block MUST begin with `::` and end with `::`. No exceptions.
- A Block encapsulates a single, discrete element of an instruction.
- The `::...::` delimiter was chosen for:
  - High visual contrast in log files
  - Syntactic simplicity
  - Resistance to collision with other data formats (JSON, XML, URLs)
  - Easy searchability (grep `::`)

**Examples of valid Blocks:**

```
::Process_Payroll::
::_Please::
::##USER_123##::
::$$49.99$$::
::%%Permission Denied%%::
::<backup_agent>::
::@@REQ_a8f3c200@@::
```

### 2.2 The Instruction Chain — Linked Blocks

An Instruction Chain is the complete, ordered expression of a single transactional thought, formed by linking one or more Blocks with a `-` (dash) separator.

**Syntax:**

```
::ORIGIN::-::CORRELATION::-::ACTION::-::DATA_BLOCKS::-::COMMAND::
```

**Canonical structure (v2.1.6):**

| Position | Block Type | Required | Description |
|----------|-----------|----------|-------------|
| 1 | Origin `::<agent_id>::` | **YES** | Who is speaking — the radio callsign |
| 2 | Correlation `::@@REQ_id@@::` | **YES** | Transaction thread — links request to response |
| 3 | Action `::Action_Name::` | **YES** | What is being done |
| 4+ | Data (various qualifiers) | Optional | Parameters, values, context |
| Terminal | Command `::_Please::` etc. | **YES** | How the transaction concludes |

**Purpose:**

- Forms a complete, transactional "thought" executable by a receiving agent
- Provides a rich, self-documenting, persistent record of an action, its parameters, and its context — all in a single readable line
- Represents a single, complete entry in the audit ledger
- Enables request/response tracing through the correlation thread

**Full example:**

```
::<backup_agent>::-::@@REQ_a8f3c200@@::-::Create_Backup::-::##ollama_data##::-::_Please::
::<backup_agent>::-::@@REQ_a8f3c200@@::-::Create_Backup::-::##ollama_data##::-::_Thank_You::
```

Same `@@REQ_a8f3c200@@` in both lines. Grep one ID, get the full conversation.

### 2.3 Parsing Logic

A receiving agent's parser operates as follows:

1. **Identify** a complete, syntactically valid Instruction Chain in the input
2. **Ignore** all text outside valid chains (narrative, log context, human-readable notes)
3. **Split** the chain string by the `-` separator to produce an ordered array of Blocks
4. **Validate** block integrity (every block starts/ends with `::`)
5. **Detect** block types from qualifier markers
6. **Extract** origin, correlation, action, data, and command from canonical positions

This is a simple, non-recursive split operation — computationally inexpensive and trivial to implement. This is a critical feature for high-throughput systems.

---

## 3. Validation Rules — "Blockchain" Integrity

### 3.1 Block Integrity

Every Block MUST start with `::` and end with `::`.

| Example | Valid? |
|---------|--------|
| `::Process_Payroll::` | ✅ |
| `Process_Payroll::` | ❌ Missing opening `::` |
| `::Process_Payroll` | ❌ Missing closing `::` |

### 3.2 Chain State Logic

After any Block closes with its `::` delimiters, the parser enters a **decision state**. The immediate next character determines the chain state:

| Next Character | Meaning |
|----------------|---------|
| `-` (dash) | **Continuation** — another Block must follow |
| ` ` (space) or end-of-line | **Termination** — the Instruction Chain is complete |
| Any other character | **Syntax error** — invalid chain |

This eliminates all ambiguity. There are exactly two valid next states after a closing `::`.

### 3.3 Transactional Integrity

Every standard Instruction Chain MUST end with one of the five official **Command Blocks** as its final block. A chain that terminates without a valid Command Block is an **incomplete thought** and is syntactically invalid.

**Exception:** The System Halt Block `::%%%%::` overrides this rule. See Section 4.C.

### 3.4 Origin Integrity (v2.1.6)

Position 1 of every chain MUST be an Origin Block `::<agent_id>::`. A chain without an origin is an **anonymous transmission** — the message came from something that doesn't have a radio callsign. This is a security-flaggable event.

### 3.5 Correlation Integrity (v2.1.6)

Position 2 of every chain MUST be a Correlation Block `::@@id@@::`. A chain without a correlation ID is an **untraceable transaction** — it cannot be linked to its request/response counterpart.

---

## 4. Block Types

### 4.A Command Blocks — Transaction Terminators

Command Blocks define the nature and completion of a transaction. They are ALWAYS the final block in a standard chain. Their "polite" naming is intentional — it encodes transaction semantics in words that a jury, a compliance officer, or a hospital administrator can understand without a decoder ring.

| Command Block | Meaning | Analogous To |
|---------------|---------|--------------|
| `::_Please::` | Standard request / action initiation | HTTP Request |
| `::_Thank_You::` | Successful completion / acknowledgment | HTTP 200 OK |
| `::_Thank_You_But_No::` | Graceful failure — understood but cannot comply | HTTP 403/422 |
| `::_Excuse_Me::` | Request for clarification — ambiguous or incomplete | HTTP 400 |
| `::_Pretty_Please::` | High-priority request — requires immediate attention | Priority flag |

### 4.B Data Blocks & Qualifiers — Typed Payloads

Data Blocks carry the content of the instruction. Optional **qualifiers** inside the block delimiters denote specific data types, enabling typed parsing without external schema.

| Qualifier | Block Type | Data Type | Purpose | Example |
|-----------|-----------|-----------|---------|---------|
| `<...>` | Origin | Agent Identity | Who is speaking — the radio callsign | `::<backup_agent>::` |
| `@@...@@` | Correlation | Transaction Thread | Links request to response | `::@@REQ_a8f3c200@@::` |
| (none) | Generic | Action / Object | High-level objects, functions, actions | `::Process_Payroll::` |
| `$$...$$` | Numeric | Financial / Numeric | Integers, floats, financial values | `::$$49.99$$::` |
| `##...##` | Identifier | ID / Static / Boolean | IDs, paths, URLs, database keys, booleans | `::##USER_123##::` |
| `%%...%%` | String | Human Text | Human-readable text, error messages, descriptions | `::%%Permission Denied%%::` |
| `??...??` | Query | Ambiguity / Question | Questions to be resolved, uncertainty flags | `::??Specify_Filename??::` |
| `&&...&&` | Version | Protocol Version | Protocol or schema version numbers | `::&&QMS_v2.1.6&&::` |
| `\|\|...\|\|` | Encrypted | Hash / Encrypted | Static string values, encrypted hashes | `::\|\|a746fg2e\|\|::` |

**Note:** The qualifier markers sit *inside* the `::` block delimiters. The block is still `::CONTENT::` — the qualifier is part of the content.

### 4.C System Halt Block — Catastrophic Failure

**Syntax:** `::%%%%::`

A special, content-free block that signals a catastrophic, unrecoverable system error requiring immediate human intervention (HITL).

**Properties:**

- Visually dense and distinct — immediately draws the eye in any log file
- A "full stop" for the AI grammar
- Emitted when an agent encounters an unhandleable situation (lost database connection, corrupted state, etc.)
- Triggers high-priority alerts in downstream monitoring systems

**Syntax Exception:** Unlike all other blocks, `::%%%%::` can be placed in ANY position within the chain. It does not require a subsequent Command Block.

**v2.1.6 Halt Postscript Convention:**

The halt block fires first — the siren. An optional reason block follows — the incident report.

```
Pattern:  ...::-::%%%%::-::%%reason%%::
```

The `::%%%%::` is the circuit breaker. The `::%%reason%%::` immediately after it carries the human-readable cause. This is the ONLY block that may follow `::%%%%::`. If present, it MUST be a String Block (`%%...%%`). No other block types may follow a halt.

| Pattern | Valid? | Description |
|---------|--------|-------------|
| `...::-::%%%%::` | ✅ | Bare halt — siren only |
| `...::-::%%%%::-::%%Database connection lost%%::` | ✅ | Halt with incident report |
| `...::-::%%%%::-::##some_id##::` | ❌ | Only `%%...%%` may follow halt |
| `...::-::%%%%::-::%%reason1%%::-::%%reason2%%::` | ❌ | Only ONE block may follow halt |

**Rationale:** A bare halt without a reason is valid but not recommended. When a human gets paged at 3 AM because of a System Halt, the first thing they ask is "what broke?" The chain itself should carry the answer.

---

## 5. Agent Identity — The Radio System (v2.1.6)

### 5.1 The Origin Block

Every chain begins with an Origin Block that identifies which agent is speaking:

```
::<agent_id>::
```

The angle bracket `<>` qualifier was chosen for maximum visual distinctiveness. In a wall of log lines with `##`, `$$`, `%%`, and `@@` qualifiers, the `<>` brackets stand out immediately — you can scan a log file and see WHO is talking before you read WHAT they said.

### 5.2 Agent Registry and Numerical IDs

Each registered agent in a TelsonBase instance receives a numerical identifier. This ID is:

- **Unique** within the instance
- **Persistent** across restarts
- **Machine-fast** to validate against a registry lookup
- **Compact** in log output

**Naming convention:**

```
::<agent_name>::           Local agent
::<agent_name/NNN>::       Local agent with numerical ID
::<instance_id/agent_name>::   Federated agent (cross-instance)
```

**Examples:**

```
::<backup_agent>::
::<backup_agent/007>::
::<alpha_instance/sync_agent/012>::
```

### 5.3 The Security Implication

An agent without a registered Origin ID is like a person on a hotel radio network without a radio. They shouldn't be talking. If a QMS chain arrives without a valid `::<...>::` in position 1:

1. The chain is flagged as **anonymous transmission**
2. A security alert is logged to the audit trail
3. The receiving system may reject the chain depending on trust policy

This is NOT authentication (that's what cryptographic signatures do). This is **provenance verification** — confirming the message traveled through legitimate internal channels. Defense in depth.

---

## 6. Correlation — Transaction Threading (v2.1.6)

### 6.1 The Correlation Block

Every chain includes a Correlation Block in position 2 that links related messages into a conversation thread:

```
::@@REQ_a8f3c200@@::
```

The `@@` qualifier wraps a unique transaction identifier. When Agent A sends a request, it generates a correlation ID. When Agent B responds, it uses the SAME correlation ID. This creates an unbroken thread from request to response across any number of interleaved log lines.

### 6.2 Why This Matters

In a system with 15 agents processing concurrently, a log file without correlation IDs is an unintelligible interleaving of unrelated statements. With correlation IDs, `grep @@REQ_a8f3c200@@` returns the complete conversation in chronological order:

```
::<backup_agent>::-::@@REQ_a8f3c200@@::-::Create_Backup::-::##ollama_data##::-::_Please::
::<backup_agent>::-::@@REQ_a8f3c200@@::-::Create_Backup::-::%%Compressing volume%%::-::_Thank_You::
```

Two lines. One thread. Complete audit trail. No Splunk query needed.

### 6.3 ID Generation

Correlation IDs are auto-generated as `REQ_` followed by 8 hex characters (from UUID4). This provides:

- 4 billion+ unique IDs per prefix (sufficient for any single instance)
- Human-scannable length (not a full UUID wall of text)
- Sortable by prefix when combined with timestamps

---

## 7. Use Cases — The AI Audit Chain in Practice

### 7.1 Simple Health Check (Ping/Pong)

```
::<monitor_agent>::-::@@REQ_0001aa00@@::-::Ping::-::_Please::
::<monitor_agent>::-::@@REQ_0001aa00@@::-::Ping::-::_Thank_You::
```

### 7.2 Request with Data

```
::<api_agent>::-::@@REQ_b4c5d6e7@@::-::Get_User_Profile::-::##USER_456##::-::_Please::
::<api_agent>::-::@@REQ_b4c5d6e7@@::-::Get_User_Profile::-::##USER_456##::-::%%John Doe%%::-::||a746fg2e96a6g7||::-::_Thank_You::
```

### 7.3 The Clarification Loop (_Excuse_Me)

```
::<archive_agent>::-::@@REQ_c7d8e9f0@@::-::Create_Archive::-::_Please::
::<archive_agent>::-::@@REQ_c7d8e9f0@@::-::Create_Archive::-::??Specify_Filename_and_Path??::-::_Excuse_Me::
::<archive_agent>::-::@@REQ_c7d8e9f0@@::-::Create_Archive::-::##/backups/monthly.zip##::-::_Please::
::<archive_agent>::-::@@REQ_c7d8e9f0@@::-::Create_Archive::-::##/backups/monthly.zip##::-::_Thank_You::
```

Note: same `@@REQ_c7d8e9f0@@` through the entire clarification exchange.

### 7.4 Graceful Failure (_Thank_You_But_No)

```
::<file_agent>::-::@@REQ_d1e2f3a4@@::-::Delete_File::-::##/etc/system.conf##::-::%%Permission Denied: Critical System File%%::-::_Thank_You_But_No::
```

### 7.5 Catastrophic Failure (System Halt)

```
::<payment_agent>::-::@@REQ_e5f6a7b8@@::-::Process_Payment::-::##TXN_9987##::-::$$15000$$::-::%%%%::-::%%Database connection lost%%::
```

The `::%%%%::` fires the siren. The `::%%Database connection lost%%::` is the incident report. A human reading this log at 3 AM knows exactly what broke without touching a terminal.

### 7.6 TelsonBase Toolroom Example

```
::<demo_agent/001>::-::@@REQ_f9a0b1c2@@::-::Tool_Checkout::-::##sha256_calculator##::-::_Please::
::<foreman>::-::@@REQ_f9a0b1c2@@::-::Tool_Checkout::-::##sha256_calculator##::-::##agent_demo_001##::-::_Thank_You::
::<demo_agent/001>::-::@@REQ_d3e4f5a6@@::-::Tool_Execute::-::##sha256_calculator##::-::%%hash_text%%::-::_Please::
::<demo_agent/001>::-::@@REQ_d3e4f5a6@@::-::Tool_Execute::-::##sha256_calculator##::-::||e3b0c44298fc1c149afb||::-::_Thank_You::
::<demo_agent/001>::-::@@REQ_b7c8d9e0@@::-::Tool_Return::-::##sha256_calculator##::-::_Thank_You::
```

### 7.7 TelsonBase Backup Example

```
::<backup_agent/003>::-::@@REQ_a1b2c3d4@@::-::Create_Backup::-::##ollama_data##::-::$$priority=1$$::-::_Please::
::<backup_agent/003>::-::@@REQ_a1b2c3d4@@::-::Create_Backup::-::##ollama_data##::-::##/backups/daily/ollama_data_20260207.tar.gz##::-::_Thank_You::
```

### 7.8 Federation Message Example

```
::<alpha_instance/sync_agent/012>::-::@@REQ_e5f6g7h8@@::-::Federation_Send::-::##instance_beta##::-::%%sync_agents%%::-::&&QMS_v2.1.6&&::-::_Please::
::<beta_instance/gateway/001>::-::@@REQ_e5f6g7h8@@::-::Federation_Send::-::%%Trust Level Insufficient%%::-::_Thank_You_But_No::
```

Note: different origin agents, same correlation ID. The request and rejection are linked.

---

## 8. Version History

| Version | Changes |
|---------|---------|
| v2.1.4 | Initial formal specification. Numeric qualifier used bare `::49.99::` |
| v2.1.5 | Numeric qualifier changed to `::$$49.99$$::`. Added `::##True##::` / `::##False##::` boolean support. Added `::||...||::` encrypted qualifier. System Halt `::%%%%::` placement exception clarified. Parsing rule: text outside valid chains MUST be ignored. Invalid examples added for clarity. |
| v2.1.6 | **Origin Block** `::<agent_id>::` — mandatory position 1. Agent identity as radio callsign. Anonymous transmissions flagged as security events. **Correlation Block** `::@@REQ_id@@::` — mandatory position 2. Transaction threading for request/response tracing. **Halt Postscript** — optional `::%%reason%%::` block may follow `::%%%%::` (one block only, must be `%%...%%` type). The siren fires first, the incident report follows. **Agent Registry** — numerical ID concept for machine-fast validation. |

---

## 9. Design Rationale — Why This Matters

### 9.1 Auditability

When the log says `::<file_agent>::-::@@REQ_d1e2f3a4@@::-::Delete_Patient_Record::-::##PATIENT_9987##::-::%%Permission Denied%%::-::_Thank_You_But_No::`, everyone in the room knows what happened. The agent identified itself. The transaction is traceable. The action is named. The data is tagged. The outcome is stated. No log parser, no Splunk query, no developer translation needed.

For HIPAA auditors, legal discovery, and compliance reviews — the QMS log line IS the audit trail.

### 9.2 The Radio Analogy

The Origin Block system works exactly like radio communications in a large facility. Every staff member has a radio with a callsign. Before you speak, you identify yourself. If someone transmits without a callsign — that's suspicious. If someone transmits with a callsign that isn't registered — that's an intruder.

The QMS Origin Block is the callsign. The Agent Registry is the roster. No radio, no trust.

### 9.3 Defense in Depth

QMS formatting as a security watermark costs almost nothing at runtime but creates a real barrier for attackers. To inject a malicious command, an attacker must:

1. **Steal** valid cryptographic credentials (bypass signature verification)
2. **Learn** the QMS grammar and format messages correctly (bypass provenance check)
3. **Know** a valid agent ID from the registry (bypass origin validation)
4. **Generate** a plausible correlation ID (bypass thread tracing)

Each layer is independently verifiable. Each layer is cheap to check. Together they create compound difficulty that makes casual injection impractical.

### 9.4 Timestamps

QMS chains do NOT carry timestamps. The log infrastructure already timestamps every line. Duplicating it inside the chain adds noise without value. Let the chain carry semantics, let the log carry time.

---

## 10. Implementation Status — TelsonBase

### 10.1 What Is Implemented (v4.6.0CC+)

The `core/qms.py` module provides:

- **Chain building:** `build_chain()` produces formal v2.1.6 chains with origin, correlation, action, data, and command blocks
- **Halt chains:** `build_halt_chain()` produces chains with `::%%%%::` and optional `::%%reason%%::` postscript
- **Chain parsing:** `parse_chain()` splits chain strings into ordered block arrays with type detection
- **Chain finding:** `find_chains()` extracts all valid chains from a block of text
- **Chain validation:** `validate_chain()` checks origin integrity, correlation integrity, transactional integrity, halt postscript rules
- **Security flagging:** `is_chain_formatted()` and `validate_chain_string()` detect and flag anonymous/missing chains
- **Audit integration:** `log_qms_chain()` writes chains to the audit trail with proper event types

### 10.2 Legacy Compatibility

Legacy functions (`format_qms()`, `parse_qms()`, `is_qms_formatted()`, `validate_qms()`) are preserved. The unified `is_qms_formatted()` function accepts BOTH legacy suffix patterns and formal chain syntax. Migration is incremental — agents adopt formal chains at their own pace.

### 10.3 Migration Path

1. New code uses `build_chain()` / `parse_chain()`
2. Existing agents continue working with legacy functions
3. `is_qms_formatted()` detects both formats transparently
4. Strict chain validation can be enabled per-agent or globally when ready

---

*QMS is an open standard. "Just because our cows eat their cabbage a certain way does not mean yours have to." — Quietfire AI*
