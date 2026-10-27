# Put this project on GitHub

Extract the ZIP, open PowerShell in its `forgefix` directory, and run the local
tests first. You do not need an API key for these checks.

```powershell
python -m unittest discover -s tests -v
python -m forgefix demo --provider scripted --out runs/my-first-demo
```

Create a **new empty repository** named `forgefix` on GitHub. Leave automatic
README, license, and gitignore generation unchecked; these files already exist.

```powershell
git init -b main
git add .
git commit -m "Build permission-limited repair agent and 50-issue benchmark"
git remote add origin https://github.com/YOUR_USERNAME/forgefix.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username. These are instructions
for a new repository; do not overwrite an existing repository's history.

CI runs unit/contract checks and a separate Docker isolation job. Review both
jobs. The included authoring evidence does not substitute for green Docker CI.

For the repository description, use: "Permission-limited software repair agent
with sandboxed tests, iterative patches, PR drafts, and a 50-issue benchmark."

Keep `.env`, credentials, and personal repositories out of commits. `runs/` is
ignored; the intentionally published `evidence/` directory contains only the
controlled scripted benchmark. Publish a live LLM report separately and label its
model, rates, date, and limitations.

