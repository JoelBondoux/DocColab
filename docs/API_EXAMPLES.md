# Provider API examples

These examples show the operations wrapped by DocColab. Production calls use the
clients in `agent/`, with OAuth/token refresh, timeouts, error handling, and
optimistic concurrency.

## Google Drive and Docs

Export a native Google document as DOCX:

```http
GET https://www.googleapis.com/drive/v3/files/{fileId}/export
    ?mimeType=application/vnd.openxmlformats-officedocument.wordprocessingml.document
Authorization: Bearer <Google OAuth access token>
```

Fetch Docs structure and revision identity:

```http
GET https://docs.googleapis.com/v1/documents/{documentId}
Authorization: Bearer <Google OAuth access token>
```

Create a Drive change notification channel:

```http
POST https://www.googleapis.com/drive/v3/files/{fileId}/watch
Authorization: Bearer <Google OAuth access token>
Content-Type: application/json

{
  "id": "<random-channel-id>",
  "type": "web_hook",
  "address": "https://public-relay.example/webhooks/google",
  "token": "<high-entropy-channel-token>"
}
```

DocColab updates the same Drive file identity through the Drive upload endpoint
so its revisions remain associated with the document.

## Microsoft Graph / OneDrive

Download and inspect:

```http
GET https://graph.microsoft.com/v1.0/drives/{driveId}/items/{itemId}
Authorization: Bearer <Graph access token>

GET https://graph.microsoft.com/v1.0/drives/{driveId}/items/{itemId}/content
Authorization: Bearer <Graph access token>
```

Replace only the version that was read:

```http
PUT https://graph.microsoft.com/v1.0/drives/{driveId}/items/{itemId}/content
Authorization: Bearer <Graph access token>
If-Match: "<previous-etag>"
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document

<DOCX bytes>
```

Track changes and persist the returned `@odata.deltaLink`:

```http
GET https://graph.microsoft.com/v1.0/drives/{driveId}/root/delta
Authorization: Bearer <Graph access token>
```

## GitHub REST

Read a Markdown blob and its optimistic concurrency SHA:

```http
GET https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}
Authorization: Bearer <fine-grained PAT>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2026-03-10
```

Commit:

```http
PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}
Authorization: Bearer <fine-grained PAT>
Content-Type: application/json

{
  "message": "sync(example): import Google Docs revision",
  "content": "<base64-markdown>",
  "branch": "develop",
  "sha": "<blob-sha-read-earlier>"
}
```

DocColab also calls refs, tags, and pull-request endpoints for version tags and
conflicts.

## OpenAI

`agent/ai/openai_client.py` uses the Responses API:

```python
response = client.responses.create(
    model="gpt-5.6-terra",
    instructions=system_prompt,
    input=markdown,
    max_output_tokens=32000,
)
updated_markdown = response.output_text
```

## Anthropic

`agent/ai/claude_client.py` uses the Messages API:

```python
message = client.messages.create(
    model="claude-sonnet-5",
    system=system_prompt,
    messages=[{"role": "user", "content": markdown}],
    max_tokens=32000,
)
```

The shared prompt requires Markdown-only output, preservation of formatting
markers and factual meaning, and explicit tone/style operations.
