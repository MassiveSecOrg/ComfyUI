import pygit2
from datetime import datetime
import sys
import os
import shutil
import filecmp
import hashlib
import json

def load_trusted_config(config_path):
    """Load trusted GPG key fingerprints and commit hashes from updater directory."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except:
        return {}

def verify_commit_signature(repo, commit_id, trusted_keys):
    """Verify GPG signature on a commit against trusted key fingerprints."""
    try:
        commit = repo.get(commit_id)
        sig, signed_data = repo.extract_signature(commit_id, 'gpgsig')
        import gpg
        ctx = gpg.Context()
        try:
            result = ctx.verify(signed_data, sig)[1]
            for r in result.signatures:
                if r.fpr in trusted_keys:
                    return True
        except:
            pass
    except:
        pass
    return False

def verify_commit_hash(commit_id, trusted_hashes):
    """Verify commit hash against allowlist of trusted immutable revisions."""
    commit_sha = str(commit_id)
    return commit_sha in trusted_hashes

def verify_update_authenticity(repo, commit_id, config):
    """Verify update authenticity via GPG signature or trusted commit hash allowlist."""
    trusted_keys = config.get('trusted_gpg_keys', [])
    trusted_hashes = config.get('trusted_commit_hashes', [])
    
    if not trusted_keys and not trusted_hashes:
        print("WARNING: No trusted GPG keys or commit hashes configured.")  # noqa: T201
        print("Update authenticity cannot be verified. Refusing to update.")  # noqa: T201
        print("Configure trusted_config.json with trusted_gpg_keys or trusted_commit_hashes.")  # noqa: T201
        return False
    
    if trusted_keys and verify_commit_signature(repo, commit_id, trusted_keys):
        return True
    
    if trusted_hashes and verify_commit_hash(commit_id, trusted_hashes):
        return True
    
    return False

def pull(repo, remote_name='origin', branch='master', trusted_config=None):
    for remote in repo.remotes:
        if remote.name == remote_name:
            remote.fetch()
            remote_master_id = repo.lookup_reference('refs/remotes/origin/%s' % (branch)).target
            
            if trusted_config is not None:
                if not verify_update_authenticity(repo, remote_master_id, trusted_config):
                    print("ERROR: Update authenticity verification failed for commit {}".format(remote_master_id))  # noqa: T201
                    print("The remote commit is not signed by a trusted key and is not in the trusted commit allowlist.")  # noqa: T201
                    raise AssertionError('Update authenticity verification failed')
            
            merge_result, _ = repo.merge_analysis(remote_master_id)
            # Up to date, do nothing
            if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                return
            # We can just fastforward
            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                repo.checkout_tree(repo.get(remote_master_id))
                try:
                    master_ref = repo.lookup_reference('refs/heads/%s' % (branch))
                    master_ref.set_target(remote_master_id)
                except KeyError:
                    repo.create_branch(branch, repo.get(remote_master_id))
                repo.head.set_target(remote_master_id)
            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                repo.merge(remote_master_id)

                if repo.index.conflicts is not None:
                    for conflict in repo.index.conflicts:
                        print('Conflicts found in:', conflict[0].path)  # noqa: T201
                    raise AssertionError('Conflicts, ahhhhh!!')

                user = repo.default_signature
                tree = repo.index.write_tree()
                repo.create_commit('HEAD',
                                    user,
                                    user,
                                    'Merge!',
                                    tree,
                                    [repo.head.target, remote_master_id])
                # We need to do this or git CLI will think we are still merging.
                repo.state_cleanup()
            else:
                raise AssertionError('Unknown merge analysis result')

pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)
repo_path = str(sys.argv[1])
repo = pygit2.Repository(repo_path)

update_py_path = os.path.realpath(__file__)
cur_path = os.path.dirname(update_py_path)
trusted_config_path = os.path.join(cur_path, "trusted_config.json")
trusted_config = load_trusted_config(trusted_config_path)

ident = pygit2.Signature('comfyui', 'comfy@ui')
try:
    print("stashing current changes")  # noqa: T201
    repo.stash(ident)
except KeyError:
    print("nothing to stash")  # noqa: T201
except:
    print("Could not stash, cleaning index and trying again.")  # noqa: T201
    repo.state_cleanup()
    repo.index.read_tree(repo.head.peel().tree)
    repo.index.write()
    try:
        repo.stash(ident)
    except KeyError:
        print("nothing to stash.")  # noqa: T201

backup_branch_name = 'backup_branch_{}'.format(datetime.today().strftime('%Y-%m-%d_%H_%M_%S'))
print("creating backup branch: {}".format(backup_branch_name))  # noqa: T201
try:
    repo.branches.local.create(backup_branch_name, repo.head.peel())
except:
    pass

print("checking out master branch")  # noqa: T201
branch = repo.lookup_branch('master')
if branch is None:
    try:
        ref = repo.lookup_reference('refs/remotes/origin/master')
    except:
        print("fetching.")  # noqa: T201
        for remote in repo.remotes:
            if remote.name == "origin":
                remote.fetch()
        ref = repo.lookup_reference('refs/remotes/origin/master')
    repo.checkout(ref)
    branch = repo.lookup_branch('master')
    if branch is None:
        repo.create_branch('master', repo.get(ref.target))
else:
    ref = repo.lookup_reference(branch.name)
    repo.checkout(ref)

print("pulling latest changes")  # noqa: T201
pull(repo, trusted_config=trusted_config)

if "--stable" in sys.argv:
    def latest_tag(repo, trusted_config):
        versions = []
        for k in repo.references:
            try:
                prefix = "refs/tags/v"
                if k.startswith(prefix):
                    version = list(map(int, k[len(prefix):].split(".")))
                    versions.append((version[0] * 10000000000 + version[1] * 100000 + version[2], k))
            except:
                pass
        versions.sort()
        for _, tag_ref in reversed(versions):
            try:
                ref = repo.lookup_reference(tag_ref)
                target_id = ref.peel().id
                if verify_update_authenticity(repo, target_id, trusted_config):
                    return tag_ref
                else:
                    print("WARNING: Tag {} (commit {}) failed authenticity verification, skipping.".format(tag_ref, target_id))  # noqa: T201
            except:
                pass
        return None
    latest_tag = latest_tag(repo, trusted_config)
    if latest_tag is not None:
        repo.checkout(latest_tag)
    else:
        print("ERROR: No verified stable tag found. Refusing to update.")  # noqa: T201
        raise AssertionError('No verified stable tag found')

print("Done!")  # noqa: T201

self_update = True
if len(sys.argv) > 2:
    self_update = '--skip_self_update' not in sys.argv

repo_update_py_path = os.path.join(repo_path, ".ci/update_windows/update.py")


req_path = os.path.join(cur_path, "current_requirements.txt")
repo_req_path = os.path.join(repo_path, "requirements.txt")


def files_equal(file1, file2):
    try:
        return filecmp.cmp(file1, file2, shallow=False)
    except:
        return False

def file_size(f):
    try:
        return os.path.getsize(f)
    except:
        return 0


if self_update and not files_equal(update_py_path, repo_update_py_path) and file_size(repo_update_py_path) > 10:
    current_commit = repo.head.target
    if verify_update_authenticity(repo, current_commit, trusted_config):
        shutil.copy(repo_update_py_path, os.path.join(cur_path, "update_new.py"))
        exit()
    else:
        print("ERROR: Current commit {} failed authenticity verification.".format(current_commit))  # noqa: T201
        print("Refusing to update updater script from unverified repository state.")  # noqa: T201
        raise AssertionError('Updater self-update authenticity verification failed')

if not os.path.exists(req_path) or not files_equal(repo_req_path, req_path):
    current_commit = repo.head.target
    if not verify_update_authenticity(repo, current_commit, trusted_config):
        print("ERROR: Cannot install requirements from unverified repository state.")  # noqa: T201
        print("Current commit {} failed authenticity verification.".format(current_commit))  # noqa: T201
    else:
        import subprocess
        try:
            subprocess.check_call([sys.executable, '-s', '-m', 'pip', 'install', '-r', repo_req_path])
            shutil.copy(repo_req_path, req_path)
        except:
            pass


stable_update_script = os.path.join(repo_path, ".ci/update_windows/update_comfyui_stable.bat")
stable_update_script_to = os.path.join(cur_path, "update_comfyui_stable.bat")

try:
    if not file_size(stable_update_script_to) > 10:
        current_commit = repo.head.target
        if verify_update_authenticity(repo, current_commit, trusted_config):
            shutil.copy(stable_update_script, stable_update_script_to)
        else:
            print("ERROR: Cannot copy stable update script from unverified repository state.")  # noqa: T201
except:
    pass

