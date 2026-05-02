# Migration: Local Editable Install to Private Index Install

## Before (developer repo workflow)

```bash
pip install -e .
```

## After (internal consumer workflow)

```bash
pip install agent-os==0.1.0-beta.3 \
  --index-url <private-index-url>
```

## Migration Steps

1. Remove editable/local package install.
2. Install the pinned beta package from private index.
3. Keep runtime/auth/secrets config files in your app deployment.
4. Run a local smoke:
   - create agent
   - init/run session
   - feedback/accept
   - evaluate/promote one learning candidate

## Notes

- Private index credentials should be configured through CI/CD secrets.
- Use pinned versions for reproducible internal rollouts.
