# Windows Updater Security Configuration

## Overview

The Windows updater now requires cryptographic verification of updates before executing repository-controlled code. This prevents supply-chain attacks where a compromised repository or Git host could deliver malicious updates.

## Configuration

Create a `trusted_config.json` file in the updater directory (same directory as `update.py`) with one or both of the following verification methods:

### Method 1: GPG Signature Verification (Recommended)

Verify commits and tags are signed by trusted GPG keys:

```json
{
  "trusted_gpg_keys": [
    "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
  ]
}
```

To find the GPG key fingerprint of ComfyUI releases:
1. Check the official ComfyUI repository for the maintainer's GPG key
2. Use `git log --show-signature` to view signed commits
3. Extract the full 40-character fingerprint

**Note:** GPG signature verification requires the `gpg` Python module. If not available, use Method 2.

### Method 2: Commit Hash Allowlist

Verify commits match a pre-approved list of immutable commit hashes:

```json
{
  "trusted_commit_hashes": [
    "abc123def456789012345678901234567890abcd",
    "def456abc789012345678901234567890123cdef"
  ]
}
```

To find commit hashes:
1. Visit the official ComfyUI repository on GitHub
2. Navigate to the commit or release you want to trust
3. Copy the full 40-character commit SHA

### Combined Configuration

You can use both methods together. The updater will accept commits that pass either verification:

```json
{
  "trusted_gpg_keys": [
    "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
  ],
  "trusted_commit_hashes": [
    "abc123def456789012345678901234567890abcd"
  ]
}
```

## Behavior

- **No configuration file**: Updates are **blocked** with an error message
- **Empty configuration**: Updates are **blocked** with an error message
- **Valid configuration**: Only verified commits/tags are accepted
- **Verification failure**: Update is **blocked** and an error is displayed

## What is Protected

The updater verifies authenticity before:
1. Checking out remote branch updates
2. Selecting and checking out stable version tags
3. Copying the updater script itself (`update.py`)
4. Installing packages from `requirements.txt`
5. Copying batch helper scripts

## Initial Setup

1. Copy `trusted_config.json.example` to `trusted_config.json`
2. Replace example values with actual trusted GPG keys or commit hashes
3. Keep `trusted_config.json` in the updater directory (not in the repository)
4. Update the configuration when new trusted releases are available

## Security Notes

- The configuration file must be in the updater directory, **not** in the repository
- Repository-controlled files cannot modify the trusted configuration
- Both GPG keys and commit hashes provide strong authenticity guarantees
- GPG signatures are preferred as they scale better for ongoing releases
- Commit hashes require manual updates but work without GPG infrastructure
