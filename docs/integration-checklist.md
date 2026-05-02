# Integration Checklist (Embedding in Existing Python Service)

- [ ] Install package from private index.
- [ ] Configure `.agent-os` workspace location per environment.
- [ ] Choose runtime mode (`local` for deterministic/dev, `openai` for provider runtime).
- [ ] Configure secret sources and validate with `agent-os secrets validate --env dev|prod`.
- [ ] Create agents with explicit `model` and `tenant_id`.
- [ ] Use typed session flow: `init -> run -> feedback -> accept`.
- [ ] Enable learning loop only through evaluate/promote flow.
- [ ] Register and bind tools with least privilege (read-only default).
- [ ] Capture audit and metrics outputs in your logging/monitoring stack.
- [ ] Add rollback handling in your operator procedures.
