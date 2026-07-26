# DocColab

DocColab is an open project exploring a Git-native collaboration method for
people and AI agents working together on Microsoft Office and Google Workspace
documents.

The goal is to make GitHub the durable system of record for document content,
change history, review, and automation while allowing contributors to keep
using familiar document editors.

## Project goals

- Represent document changes in a form that Git can version and review.
- Preserve useful document structure and metadata across editor round trips.
- Attribute changes to human collaborators and AI agents.
- Support proposals, comments, approvals, and conflict resolution.
- Connect Microsoft Office and Google Workspace editing flows to GitHub.
- Keep the storage format open, auditable, and recoverable.

## Proposed collaboration loop

1. Import or synchronize a document from Microsoft 365 or Google Workspace.
2. Convert its editable structure into a deterministic, Git-friendly form.
3. Let people and AI agents work in branches or isolated workspaces.
4. Review changes through pull requests with document-aware previews.
5. Merge approved changes and synchronize the result back to the document
   platform.

## Status

DocColab is at the concept and design stage. Initial work will define the
document model, synchronization semantics, identity and attribution model, and
the smallest end-to-end prototype.

## Contributing

Ideas, design proposals, experiments, and implementation contributions are
welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull
request.

## Security

Please report potential vulnerabilities according to
[SECURITY.md](SECURITY.md).

## License

DocColab is available under the [MIT License](LICENSE).
