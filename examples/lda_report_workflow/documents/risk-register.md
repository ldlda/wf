# Risk Register

Material risks:

- Title and product framing can overstate the implemented autonomous-agent
  layer if not explained carefully.
- Evaluation evidence is stronger as systems evidence than as a controlled
  empirical model comparison.
- File-backed stores are useful for auditability but not a production
  transaction boundary.
- The Workflow Console needs a strict loopback-only first slice to avoid
  becoming an arbitrary RPC proxy.

Mitigations:

- Keep the agent/substrate boundary explicit in the thesis and defense.
- Present challenge data as bounded operational evidence.
- Defer production storage, auth, and remote proxying to future work.
