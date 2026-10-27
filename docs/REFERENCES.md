# Implementation references

Consulted while implementing this version:

- [Docker container run reference](https://docs.docker.com/reference/cli/docker/container/run/):
  read-only filesystems, no-new-privileges, capabilities, resource and network options.
- [Docker engine security](https://docs.docker.com/engine/security/):
  daemon and shared-kernel trust boundaries.
- [Docker rootless mode](https://docs.docker.com/engine/security/rootless/):
  an optional operator hardening choice.
- [Chat Completions API reference](https://platform.openai.com/docs/api-reference/chat):
  JSON-object responses, completion limits, and reported usage fields.

Model support and rates are deliberately operator-configured. No current model
pricing or unverified model-quality numbers are embedded in this project.

