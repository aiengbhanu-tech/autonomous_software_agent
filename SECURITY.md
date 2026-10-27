# Security boundaries and supported use

ForgeFix treats issue text, repository files, model output, and test output as
untrusted data. Its primary defense is a narrow capability surface, not the
model's willingness to follow a security prompt.

## Model permissions

- Read only the bounded context selected by the orchestrator.
- Propose complete contents for at most three existing Python source files.
- Receive bounded check feedback and propose a revision within fixed budgets.

There is no shell tool, arbitrary subprocess API, package installation, generic
file write, Git execution, network tool, or publish capability exposed to the
model. It cannot choose the runner, image, runtime, mounts, environment, test
command, credentials, endpoint, budget, or original repository location.

## Host and sandbox permissions

Only the trusted Docker backend invokes host subprocesses: image inspection,
fixed container execution, and named-container cleanup. It uses argument arrays
with no shell. Missing Docker or a missing prebuilt image prevents execution.

The container has a read-only filesystem and repository mount, a small ephemeral
`/tmp`, no network, no API key or inherited host environment, no Docker socket,
non-root UID 65534, no Linux capabilities, and no-new-privileges. It is limited
to one CPU, 256 MB memory, 64 processes, bounded file sizes/descriptors, a wall
deadline, and 32 KB captured output. Repository hooks and build scripts are not run.
The orchestrator resolves a trusted local image ID before running; pulls are off.
Retain the default Docker seccomp/AppArmor policies. Never run the orchestrator
with `--privileged`, an unconfined Docker daemon policy, or a shared production socket.

The local Docker daemon and host administrator are trusted. Use an isolated local
Docker context, ideally rootless Docker, and a disposable VM. For actively hostile
repositories, configure gVisor (`--runtime runsc`) or a microVM boundary. This
implementation does not provision a microVM or prove kernel isolation.

## Controlled interpreter boundary

The AST backend does not execute Python bytecode from source. It accepts one
function with a single return expression and evaluates explicit node types using
bounded plain values. Only named builtins and enumerated methods on exact built-in
types are supported. Arbitrary attributes, file/network access, imports, loops,
recursion and dynamic execution are unavailable. It is designed for the supplied
small trusted contracts; importing Python source is never an AST-backend fallback.

## Limits of correctness and isolation

- Container isolation shares the host kernel. Vulnerable kernels, runtimes, image
  contents, and operator configuration are outside this project's guarantees.
- Full Python source can sabotage in-process unittest results, monkeypatch the
  test framework, or spoof output. Read-only test files prevent filesystem edits,
  not runtime test interference. General test success is provisional and requires
  review. The independent AST contract evaluator has a narrower interface.
- The trusted image's standard library includes subprocess APIs. Candidate code
  can create child processes **inside** its resource-limited container; the agent
  cannot issue arbitrary host commands. This is not a syscall whitelist sandbox.
- Dependencies, build hooks, custom test commands, new files, and config changes
  are unsupported. Do not relax policy automatically to make a patch pass.
- Snapshot and output storage must be private to the operator. Concurrent local
  attackers modifying snapshot paths are outside the threat model. The initial
  snapshot ignores hidden files but does not guarantee removal of secrets embedded
  in normal source files. Selected source is sent to the configured LLM provider.
- Provider rate estimates are not billing guarantees. HTTPS endpoints and credentials
  are operator-selected. Redirects and automatic retries are disabled.
- Automatic resume is not implemented. Preserve partial JSONL checkpoints and use
  a new output directory after interruption.

Report security issues privately to the repository owner through their configured
GitHub security contact after publishing this repository. No contact address is
invented in this template.

