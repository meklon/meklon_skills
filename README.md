# meklon_skills

A collection of Claude Code plugins.

The repository is a **marketplace** called `meklon-skills` (a monorepo): one
`marketplace.json` at the root lists every plugin, and each plugin lives in
`plugins/<name>/`. Add the marketplace once, then install the plugins you need.

| Plugin | When it triggers | What it gives |
|---|---|---|
| [`diagrams`](plugins/diagrams/README.md) | You need a diagram, a status board, a roadmap or an incident write-up for a report or a client | Static PNG/SVG in one consistent style: three themes, an overlap linter and a contrast check; examples in the plugin README |

![Example: a backup design drawn by the diagrams skill](plugins/diagrams/docs/example-velero-backup.png)

## Quick start

Run in Claude Code:

```
/plugin marketplace add meklon/meklon_skills
/plugin install diagrams@meklon-skills
```

## Updating

```
/plugin marketplace update meklon-skills
/reload-plugins
```

The first command pulls the latest `marketplace.json` and plugins from the
repository; the second reloads them in the current session without restarting
Claude Code.

## Repository layout

```
.claude-plugin/marketplace.json     # the marketplace's plugin list
plugins/<name>/.claude-plugin/plugin.json
plugins/<name>/skills/<skill>/SKILL.md
plugins/<name>/README.md            # plugin description and examples
```

A new plugin is a folder in `plugins/` plus an entry in `marketplace.json`; bump
the version in `plugin.json` on changes so that `marketplace update` picks them up.

## License

MIT — see [LICENSE](LICENSE). The bundled IBM Plex fonts are under the SIL Open
Font License 1.1.
