# Unreal branch switching

- Save work and close this project's Unreal Editor before switching, pulling, merging, or discarding asset changes. Reopen it after Git finishes so it loads the selected branch from disk.
- Commit new Content assets and their World Partition external actors together. Untracked `.uasset` files are real content, not disposable caches.
- `Saved/`, `Intermediate/`, `Binaries/`, and `DerivedDataCache/` are local generated files. The project `.gitignore` excludes them; do not force-add them. Ignore rules do not remove files already tracked by Git.
- Before discarding unexplained changes, inspect them and preserve a backup (`git stash push --include-untracked`). Do not reapply a backup whose contents already exist in the merged branch.
- Binary Blueprint conflicts require editor-based integration. For the September 16 merge, keep SB's runner camera and enemy collision behavior alongside main's weapon grip scale and projectile tracer.

## September 16 recovery

The main working tree contained 153 untracked assets and five modified assets, all byte-identical to SB. SB also tracked ten generated files. The residual assets were backed up in a named stash, SB was integrated into main, and the generated files were removed from tracking while retaining local copies.
