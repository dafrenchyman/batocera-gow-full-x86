# Frontend package manager

## Question

Choose npm or pnpm as the prescribed frontend default. The choice is unresolved.

## Findings

- Both manage dependencies declared in package.json, support scripts, and support multi-package workspaces. npm workspace support is documented at https://docs.npmjs.com/cli/v11/using-npm/workspaces/; pnpm workspace support at https://pnpm.io/workspaces.
- npm's default install strategy is hoisted. Its linked strategy can provide stricter isolation; dependency isolation is not exclusive to pnpm. npm ci requires an existing lockfile, fails when it disagrees with package.json, and leaves manifests and lockfiles unchanged. Source: https://docs.npmjs.com/cli/v11/commands/npm-ci/.
- pnpm's default isolated layout links packages through a content-addressable store. This can reduce duplicate package storage across projects and makes direct undeclared dependencies less likely to resolve by accident. Its documentation also describes internal hoisting for ecosystem compatibility. Source: https://pnpm.io/symlinked-node-modules-structure.
- pnpm offers the workspace: protocol to require a dependency to resolve to a local workspace package, rather than silently fall back to the registry. Source: https://pnpm.io/workspaces.
- pnpm requires a separate installation or provisioning step. Installation requirements vary by release; do not assume that all pnpm releases have the same runtime requirements. Source: https://pnpm.io/installation.

## Decision impact

npm favors minimal setup and familiar commands. pnpm favors an isolated default dependency layout and explicit local workspace dependencies. Both are viable for a single React app and for workspaces. Workspace support alone is not a reason to reject npm.

Recommend pnpm for the reusable template if the extra tool provisioning is acceptable. Recommend npm when minimal contributor setup is the stronger requirement. No local speed benchmark has been performed; installation speed is not established for future forks.
