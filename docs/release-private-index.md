# Distribution Workflow (`v0.1.0-beta.3`)

## 1) Build Artifacts

```bash
python scripts/release/build_dist.py
```

Expected: `dist/` contains both `.whl` and `.tar.gz`.

## 2) Verify Install from Artifact

```bash
python scripts/release/verify_install.py
```

This creates a clean virtualenv, installs the wheel, and runs a minimal SDK smoke flow.

## 3) Distribution Option A: Publish to Private Index (Optional)

Set:

- `AGENT_OS_PRIVATE_INDEX_URL`
- `AGENT_OS_PRIVATE_INDEX_USERNAME`
- `AGENT_OS_PRIVATE_INDEX_PASSWORD`

Then run:

```bash
python scripts/release/publish_private_index.py
```

## 4) Distribution Option B: Wheel-Only Distribution (Accepted)

If you do not have a private index, distribute the wheel directly:

```bash
pip install dist/agent_os-0.1.0b3-py3-none-any.whl
```

For other machines, copy the wheel file and run:

```bash
pip install agent_os-0.1.0b3-py3-none-any.whl
```

## 5) Consumer Verification

In a clean environment:

```bash
# private-index path:
pip install agent-os==0.1.0-beta.3 --index-url <private-index-url>

# wheel-only path:
pip install dist/agent_os-0.1.0b3-py3-none-any.whl

python examples/proposal_agent_app.py
```
